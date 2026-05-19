import 'package:flutter_test/flutter_test.dart';
import 'package:omnisource/data/models/playlist_model.dart';
import 'package:omnisource/presentation/bloc/library/library_cubit.dart';
import 'package:omnisource/presentation/bloc/library/library_state.dart';

import 'test_fakes.dart';

void main() {
  group('LibraryCubit', () {
    late FakeContentRepository contentRepository;
    late FakePlaylistRepository playlistRepository;
    late LibraryCubit cubit;

    final playlistA = PlaylistModel(
      id: 'p1',
      title: 'Playlist A',
      items: const [],
    );
    final playlistB = PlaylistModel(
      id: 'p2',
      title: 'Playlist B',
      items: const [],
    );

    setUp(() {
      contentRepository = FakeContentRepository();
      playlistRepository = FakePlaylistRepository();
      cubit = LibraryCubit(
        contentRepository: contentRepository,
        playlistRepository: playlistRepository,
      );

      contentRepository.favoritesResponse = [
        makeContent(id: 'f1', externalId: 'f1', type: 'movie', title: 'Fav 1'),
      ];
      playlistRepository.playlistsResponse = [playlistA, playlistB];
      playlistRepository.contentByPlaylistId['p1'] = [
        makeContent(id: 'i1', externalId: 'i1', type: 'movie', title: 'Item 1'),
      ];
      playlistRepository.contentByPlaylistId['p2'] = [
        makeContent(id: 'i2', externalId: 'i2', type: 'music', title: 'Item 2'),
      ];
    });

    tearDown(() async {
      await cubit.close();
    });

    test('loadLibraryData emits loaded state with playlist items', () async {
      final emitted = <LibraryState>[];
      final sub = cubit.stream.listen(emitted.add);

      await cubit.loadLibraryData();
      await sub.cancel();

      expect(emitted.any((state) => state is LibraryLoading), isTrue);
      expect(cubit.state, isA<LibraryLoaded>());
      final state = cubit.state as LibraryLoaded;
      expect(state.favorites.length, 1);
      expect(state.playlists.length, 2);
      expect(state.playlistItemsById['p1']?.length, 1);
      expect(state.playlistItemsById['p2']?.length, 1);
    });

    test(
      'loadLibraryData tolerates playlist-content failures per playlist',
      () async {
        playlistRepository.playlistContentErrorById['p2'] = Exception(
          'broken playlist',
        );

        await cubit.loadLibraryData();

        expect(cubit.state, isA<LibraryLoaded>());
        final state = cubit.state as LibraryLoaded;
        expect(state.playlistItemsById['p1']?.length, 1);
        expect(state.playlistItemsById['p2'], isEmpty);
      },
    );

    test('fresh load cache avoids immediate second fetch', () async {
      await cubit.loadLibraryData();
      final favoritesCallsAfterFirst = contentRepository.favoritesCalls;
      final playlistCallsAfterFirst = playlistRepository.getPlaylistsCalls;

      await cubit.loadLibraryData();

      expect(contentRepository.favoritesCalls, favoritesCallsAfterFirst);
      expect(playlistRepository.getPlaylistsCalls, playlistCallsAfterFirst);
    });

    test('createPlaylist triggers repository call and forced reload', () async {
      await cubit.loadLibraryData();
      final initialFavoritesCalls = contentRepository.favoritesCalls;

      await cubit.createPlaylist('New Playlist');

      expect(playlistRepository.createCalls, 1);
      expect(playlistRepository.lastCreatedTitle, 'New Playlist');
      expect(
        contentRepository.favoritesCalls,
        greaterThan(initialFavoritesCalls),
      );
      expect(cubit.state, isA<LibraryLoaded>());
    });

    test('getPlaylistItems returns empty when state is not loaded', () {
      expect(cubit.getPlaylistItems('missing'), isEmpty);
    });

    test('toggleFavorite updates favorites optimistically', () async {
      await cubit.loadLibraryData();
      final item = makeContent(
        id: 'x',
        externalId: 'ext-x',
        type: 'movie',
        title: 'X',
      );
      final initialFavoritesCalls = contentRepository.favoritesCalls;

      await cubit.toggleFavorite(item);

      expect(contentRepository.toggleLikeCalls, 1);
      expect(contentRepository.favoritesCalls, initialFavoritesCalls);
      expect(cubit.state, isA<LibraryLoaded>());
      final state = cubit.state as LibraryLoaded;
      expect(state.favorites.first.externalId, 'ext-x');
    });

    test('toggleFavorite rolls back optimistic update on failure', () async {
      await cubit.loadLibraryData();
      contentRepository.toggleLikeError = Exception('network');
      final item = makeContent(
        id: 'x',
        externalId: 'ext-x',
        type: 'movie',
        title: 'X',
      );

      await cubit.toggleFavorite(item);

      expect(contentRepository.toggleLikeCalls, 1);
      expect(cubit.state, isA<LibraryLoaded>());
      final state = cubit.state as LibraryLoaded;
      expect(
        state.favorites.any((favorite) => favorite.externalId == 'ext-x'),
        isFalse,
      );
    });

    test('loadLibraryData emits error state when root fetch fails', () async {
      contentRepository.favoritesError = Exception('favorites broken');

      await cubit.loadLibraryData(force: true);

      expect(cubit.state, isA<LibraryError>());
      expect((cubit.state as LibraryError).message, contains('Failed to load'));
    });

    test('removeItemsFromPlaylist forwards all external ids', () async {
      await cubit.loadLibraryData();

      await cubit.removeItemsFromPlaylist('p1', ['i1', 'i2', 'i3']);

      expect(playlistRepository.removeCalls, 3);
    });

    test('deletePlaylist forwards id and forces reload', () async {
      await cubit.loadLibraryData();
      final initialFavoritesCalls = contentRepository.favoritesCalls;

      await cubit.deletePlaylist('p1');

      expect(playlistRepository.deleteCalls, 1);
      expect(playlistRepository.lastDeletedId, 'p1');
      expect(
        contentRepository.favoritesCalls,
        greaterThan(initialFavoritesCalls),
      );
      expect(cubit.state, isA<LibraryLoaded>());
    });

    test('updatePlaylist forwards payload and forces reload', () async {
      await cubit.loadLibraryData();
      final initialFavoritesCalls = contentRepository.favoritesCalls;

      await cubit.updatePlaylist(
        'p2',
        title: 'Updated title',
        description: 'Updated desc',
      );

      expect(playlistRepository.updateCalls, 1);
      expect(playlistRepository.lastUpdatedId, 'p2');
      expect(
        contentRepository.favoritesCalls,
        greaterThan(initialFavoritesCalls),
      );
      expect(cubit.state, isA<LibraryLoaded>());
    });

    test('addItemToPlaylist forwards item and forces reload', () async {
      await cubit.loadLibraryData();
      final initialFavoritesCalls = contentRepository.favoritesCalls;
      final item = makeContent(
        id: 'n1',
        externalId: 'n1',
        type: 'music',
        title: 'New track',
      );

      await cubit.addItemToPlaylist('p1', item);

      expect(playlistRepository.addCalls, 1);
      expect(
        contentRepository.favoritesCalls,
        greaterThan(initialFavoritesCalls),
      );
      expect(
        playlistRepository.contentByPlaylistId['p1']?.any(
          (entry) => entry.externalId == 'n1',
        ),
        isTrue,
      );
    });

    test('removeFavorites toggles all provided items then reloads', () async {
      await cubit.loadLibraryData();
      final initialFavoritesCalls = contentRepository.favoritesCalls;
      final items = [
        makeContent(id: 'a', externalId: 'a', type: 'movie', title: 'A'),
        makeContent(id: 'b', externalId: 'b', type: 'book', title: 'B'),
      ];

      await cubit.removeFavorites(items);

      expect(contentRepository.toggleLikeCalls, 2);
      expect(
        contentRepository.favoritesCalls,
        greaterThan(initialFavoritesCalls),
      );
    });
  });
}
