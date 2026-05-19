import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter/services.dart';

import '../../domain/entities/unified_content.dart';
import '../bloc/library/library_cubit.dart';
import '../bloc/library/library_state.dart';

class ContentQuickActions {
  static Future<void> show(
    BuildContext context,
    UnifiedContent item, {
    String source = 'card',
  }) async {
    final cubit = context.read<LibraryCubit>();
    final state = cubit.state;
    final isLiked = state is LibraryLoaded
        ? state.favorites.any((fav) => fav.externalId == item.externalId)
        : false;

    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: const Color(0xFF1C1C1E),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (sheetContext) {
        return SafeArea(
          child: Wrap(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                child: Text(
                  item.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              _QuickActionTile(
                icon: isLiked
                    ? CupertinoIcons.heart_slash
                    : CupertinoIcons.heart_fill,
                title: isLiked ? 'Remove from favorites' : 'Add to favorites',
                onTap: () async {
                  Navigator.pop(sheetContext);
                  final updated = await cubit.toggleFavorite(item);
                  if (!context.mounted) return;
                  _showSnack(
                    context,
                    updated
                        ? isLiked
                              ? 'Removed from favorites'
                              : 'Added to favorites'
                        : 'Could not update favorites',
                  );
                },
              ),
              _QuickActionTile(
                icon: CupertinoIcons.music_note_list,
                title: 'Add to playlist',
                onTap: () async {
                  Navigator.pop(sheetContext);
                  await _showPlaylistPicker(context, item);
                },
              ),
              _QuickActionTile(
                icon: CupertinoIcons.link,
                title: 'Copy source link',
                onTap: () async {
                  Navigator.pop(sheetContext);
                  final link = _sourceLinkFor(item);
                  if (link == null) {
                    _showSnack(context, 'Source link is not available');
                    return;
                  }
                  await Clipboard.setData(ClipboardData(text: link));
                  if (!context.mounted) return;
                  _showSnack(context, 'Source link copied');
                },
              ),
              _QuickActionTile(
                icon: CupertinoIcons.doc_on_doc,
                title: 'Copy title',
                onTap: () async {
                  Navigator.pop(sheetContext);
                  await Clipboard.setData(ClipboardData(text: item.title));
                  if (!context.mounted) return;
                  _showSnack(context, 'Title copied');
                },
              ),
              const SizedBox(height: 6),
              _QuickActionTile(
                icon: CupertinoIcons.info_circle,
                title: 'Card source: $source',
                disabled: true,
                onTap: () {},
              ),
              const SizedBox(height: 12),
            ],
          ),
        );
      },
    );
  }

  static Future<void> _showPlaylistPicker(
    BuildContext context,
    UnifiedContent item,
  ) async {
    final cubit = context.read<LibraryCubit>();
    var state = cubit.state;
    if (state is! LibraryLoaded) {
      await cubit.loadLibraryData(force: true, showLoader: false);
      if (!context.mounted) return;
      state = cubit.state;
    }
    if (state is! LibraryLoaded || state.playlists.isEmpty) {
      _showSnack(context, 'Create a playlist first');
      return;
    }
    final loadedState = state;

    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: const Color(0xFF1C1C1E),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (playlistContext) {
        return SafeArea(
          child: ListView(
            shrinkWrap: true,
            children: [
              const Padding(
                padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
                child: Text(
                  'Add to playlist',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                ),
              ),
              ...loadedState.playlists.map((playlist) {
                final count =
                    loadedState.playlistItemsById[playlist.id]?.length ?? 0;
                return ListTile(
                  title: Text(playlist.title),
                  subtitle: Text('$count items'),
                  trailing: const Icon(CupertinoIcons.add_circled),
                  onTap: () async {
                    await cubit.addItemToPlaylist(playlist.id, item);
                    if (!context.mounted) return;
                    if (!playlistContext.mounted) return;
                    Navigator.pop(playlistContext);
                    _showSnack(context, 'Added to "${playlist.title}"');
                  },
                );
              }),
              const SizedBox(height: 10),
            ],
          ),
        );
      },
    );
  }

  static String? _sourceLinkFor(UnifiedContent item) {
    switch (item.type) {
      case 'movie':
        return 'https://www.themoviedb.org/movie/${item.externalId}';
      case 'music':
        return 'https://open.spotify.com/track/${item.externalId}';
      case 'book':
        return 'https://books.google.com/books?id=${item.externalId}';
      default:
        return null;
    }
  }

  static void _showSnack(BuildContext context, String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), behavior: SnackBarBehavior.floating),
    );
  }
}

class _QuickActionTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final VoidCallback onTap;
  final bool disabled;

  const _QuickActionTile({
    required this.icon,
    required this.title,
    required this.onTap,
    this.disabled = false,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      enabled: !disabled,
      leading: Icon(icon, size: 20),
      title: Text(
        title,
        style: TextStyle(color: disabled ? Colors.white54 : Colors.white),
      ),
      onTap: disabled ? null : onTap,
    );
  }
}
