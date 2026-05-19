import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/utils/app_logger.dart';
import '../../../domain/repositories/content_repository.dart';
import '../../../domain/repositories/playlist_repository.dart';
import '../../../domain/entities/unified_content.dart';
import 'library_state.dart';

class LibraryCubit extends Cubit<LibraryState> {
  final ContentRepository contentRepository;
  final PlaylistRepository playlistRepository;
  static const Duration _freshWindow = Duration(seconds: 15);
  DateTime? _lastLoadedAt;
  Future<void>? _inflightLoad;
  final Set<String> _pendingFavoriteToggles = {};

  LibraryCubit({
    required this.contentRepository,
    required this.playlistRepository,
  }) : super(LibraryInitial());

  Future<LibraryLoaded> _fetchLoadedState() async {
    final favorites = await contentRepository.getFavorites();
    final playlists = await playlistRepository.getPlaylists();
    final playlistItemsById = <String, List<UnifiedContent>>{};

    await Future.wait(
      playlists.map((playlist) async {
        try {
          playlistItemsById[playlist.id] = await playlistRepository
              .getPlaylistContent(playlist.id);
        } catch (e, st) {
          AppLogger.error(
            'Failed to load playlist content for ${playlist.id}',
            error: e,
            stackTrace: st,
            name: 'LibraryCubit',
          );
          playlistItemsById[playlist.id] = const [];
        }
      }),
    );

    return LibraryLoaded(
      favorites: favorites,
      playlists: playlists,
      playlistItemsById: playlistItemsById,
    );
  }

  Future<void> loadLibraryData({
    bool force = false,
    bool showLoader = true,
  }) async {
    final now = DateTime.now();
    if (!force &&
        state is LibraryLoaded &&
        _lastLoadedAt != null &&
        now.difference(_lastLoadedAt!) < _freshWindow) {
      return;
    }

    final existing = _inflightLoad;
    if (existing != null) {
      return existing;
    }

    final future = _loadInternal(showLoader: showLoader);
    _inflightLoad = future;
    await future;
  }

  Future<void> _loadInternal({required bool showLoader}) async {
    if (showLoader && state is! LibraryLoaded) {
      emit(LibraryLoading());
    }
    try {
      emit(await _fetchLoadedState());
      _lastLoadedAt = DateTime.now();
    } catch (e, st) {
      AppLogger.error(
        'Library load failed',
        error: e,
        stackTrace: st,
        name: 'LibraryCubit',
      );
      emit(LibraryError('Failed to load library data'));
    } finally {
      _inflightLoad = null;
    }
  }

  Future<void> createPlaylist(String title) async {
    try {
      await playlistRepository.createPlaylist(title);
      AppLogger.info('Playlist created: $title', name: 'LibraryCubit');
    } catch (e, st) {
      AppLogger.error(
        'Create playlist failed',
        error: e,
        stackTrace: st,
        name: 'LibraryCubit',
      );
    } finally {
      await loadLibraryData(force: true, showLoader: false);
    }
  }

  Future<void> deletePlaylist(String id) async {
    try {
      await playlistRepository.deletePlaylist(id);
      AppLogger.info('Playlist deleted: $id', name: 'LibraryCubit');
    } catch (e, st) {
      AppLogger.error(
        'Delete playlist failed',
        error: e,
        stackTrace: st,
        name: 'LibraryCubit',
      );
    } finally {
      await loadLibraryData(force: true, showLoader: false);
    }
  }

  Future<void> updatePlaylist(
    String id, {
    String? title,
    String? description,
  }) async {
    try {
      await playlistRepository.updatePlaylist(
        id,
        title: title,
        description: description,
      );
      AppLogger.info('Playlist updated: $id', name: 'LibraryCubit');
    } catch (e, st) {
      AppLogger.error(
        'Update playlist failed',
        error: e,
        stackTrace: st,
        name: 'LibraryCubit',
      );
    } finally {
      await loadLibraryData(force: true, showLoader: false);
    }
  }

  Future<bool> toggleFavorite(UnifiedContent item) async {
    final key = _contentKey(item);
    if (_pendingFavoriteToggles.contains(key)) return false;

    final currentState = state;
    bool? rollbackToLiked;

    if (currentState is LibraryLoaded) {
      final wasLiked = _containsContent(currentState.favorites, item);
      rollbackToLiked = wasLiked;
      emit(_setFavoriteState(currentState, item, liked: !wasLiked));
    }

    _pendingFavoriteToggles.add(key);
    try {
      await contentRepository.toggleLike(item);
      AppLogger.info(
        'Favorite toggled: ${item.externalId}',
        name: 'LibraryCubit',
      );
      return true;
    } catch (e, st) {
      final latestState = state;
      if (rollbackToLiked != null && latestState is LibraryLoaded) {
        emit(_setFavoriteState(latestState, item, liked: rollbackToLiked));
      }
      AppLogger.error(
        'Toggle favorite failed',
        error: e,
        stackTrace: st,
        name: 'LibraryCubit',
      );
      return false;
    } finally {
      _pendingFavoriteToggles.remove(key);
    }
  }

  Future<void> addItemToPlaylist(String playlistId, UnifiedContent item) async {
    try {
      await playlistRepository.addToPlaylist(playlistId, item);
      AppLogger.info(
        'Added to playlist: $playlistId -> ${item.externalId}',
        name: 'LibraryCubit',
      );
    } catch (e, st) {
      AppLogger.error(
        'Add to playlist failed',
        error: e,
        stackTrace: st,
        name: 'LibraryCubit',
      );
    } finally {
      await loadLibraryData(force: true, showLoader: false);
    }
  }

  Future<void> removeItemsFromPlaylist(
    String playlistId,
    List<String> contentRefs,
  ) async {
    try {
      await Future.wait(
        contentRefs.map((contentRef) {
          return playlistRepository.removeFromPlaylist(playlistId, contentRef);
        }),
      );
      AppLogger.info(
        'Removed ${contentRefs.length} items from $playlistId',
        name: 'LibraryCubit',
      );
    } catch (e, st) {
      AppLogger.error(
        'Remove from playlist failed',
        error: e,
        stackTrace: st,
        name: 'LibraryCubit',
      );
    } finally {
      await loadLibraryData(force: true, showLoader: false);
    }
  }

  Future<void> removeFavorites(List<UnifiedContent> items) async {
    try {
      await Future.wait(items.map(contentRepository.toggleLike));
      AppLogger.info(
        'Removed ${items.length} items from favorites',
        name: 'LibraryCubit',
      );
    } catch (e, st) {
      AppLogger.error(
        'Remove favorites failed',
        error: e,
        stackTrace: st,
        name: 'LibraryCubit',
      );
    } finally {
      await loadLibraryData(force: true, showLoader: false);
    }
  }

  List<UnifiedContent> getPlaylistItems(String playlistId) {
    final currentState = state;
    if (currentState is! LibraryLoaded) return const [];
    return currentState.playlistItemsById[playlistId] ?? const [];
  }

  LibraryLoaded _setFavoriteState(
    LibraryLoaded source,
    UnifiedContent item, {
    required bool liked,
  }) {
    final existing = source.favorites;
    final contains = _containsContent(existing, item);

    if (liked && !contains) {
      return source.copyWith(favorites: [item, ...existing]);
    }
    if (!liked && contains) {
      return source.copyWith(
        favorites: existing
            .where((favorite) => _contentKey(favorite) != _contentKey(item))
            .toList(),
      );
    }
    return source;
  }

  bool _containsContent(List<UnifiedContent> items, UnifiedContent target) {
    final targetKey = _contentKey(target);
    return items.any((item) => _contentKey(item) == targetKey);
  }

  String _contentKey(UnifiedContent item) {
    final externalId = item.externalId.trim();
    if (externalId.isNotEmpty) return '${item.type}:$externalId';
    return '${item.type}:${item.id}';
  }
}
