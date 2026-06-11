import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:omnisource/data/models/playlist_model.dart';
import 'package:omnisource/domain/entities/unified_content.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../core/utils/content_display.dart';
import '../../../core/theme/app_theme.dart';
import '../../bloc/library/library_cubit.dart';
import '../../bloc/library/library_state.dart';
import '../../widgets/app_feedback.dart';
import 'content_card.dart';
import 'playlist_detail_screen.dart';
import 'smart_library_screen.dart';

class LibraryScreen extends StatefulWidget {
  const LibraryScreen({super.key});

  @override
  State<LibraryScreen> createState() => _LibraryScreenState();
}

class _LibraryScreenState extends State<LibraryScreen> {
  static const _recentPageSize = 10;

  bool _isPlaylistEditMode = false;
  bool _isDeletingPlaylists = false;
  int _recentVisibleCount = _recentPageSize;
  final Set<String> _selectedPlaylistIds = {};

  @override
  void initState() {
    super.initState();
    context.read<LibraryCubit>().loadLibraryData();
  }

  void _togglePlaylistEditor() {
    setState(() {
      _isPlaylistEditMode = !_isPlaylistEditMode;
      _selectedPlaylistIds.clear();
    });
  }

  void _togglePlaylistSelection(String playlistId) {
    setState(() {
      if (_selectedPlaylistIds.contains(playlistId)) {
        _selectedPlaylistIds.remove(playlistId);
      } else {
        _selectedPlaylistIds.add(playlistId);
      }
    });
  }

  void _selectAllPlaylists(List<PlaylistModel> playlists) {
    setState(() {
      if (_selectedPlaylistIds.length == playlists.length) {
        _selectedPlaylistIds.clear();
      } else {
        _selectedPlaylistIds
          ..clear()
          ..addAll(playlists.map((playlist) => playlist.id));
      }
    });
  }

  Future<void> _deleteSelectedPlaylists() async {
    if (_selectedPlaylistIds.isEmpty || _isDeletingPlaylists) return;
    final ids = _selectedPlaylistIds.toList(growable: false);

    setState(() => _isDeletingPlaylists = true);
    try {
      for (final id in ids) {
        await context.read<LibraryCubit>().deletePlaylist(id);
      }
      if (!mounted) return;
      setState(() {
        _selectedPlaylistIds.clear();
        _isPlaylistEditMode = false;
      });
    } finally {
      if (mounted) {
        setState(() => _isDeletingPlaylists = false);
      }
    }
  }

  void _renameSelectedPlaylist(List<PlaylistModel> playlists) {
    if (_selectedPlaylistIds.length != 1) return;
    final playlist = playlists.firstWhere(
      (item) => item.id == _selectedPlaylistIds.first,
    );
    _showPlaylistFormSheet(
      title: 'Rename Playlist',
      initialTitle: playlist.title,
      initialDescription: playlist.description,
      submitLabel: 'Save',
      onSubmit: (title, description) async {
        await context.read<LibraryCubit>().updatePlaylist(
          playlist.id,
          title: title,
          description: description,
        );
        if (!mounted) return;
        setState(() {
          _selectedPlaylistIds.clear();
          _isPlaylistEditMode = false;
        });
      },
    );
  }

  void _showCreatePlaylistSheet() {
    _showPlaylistFormSheet(
      title: 'New Playlist',
      submitLabel: 'Create',
      onSubmit: (title, description) async {
        await context.read<LibraryCubit>().createPlaylist(title);
      },
    );
  }

  Future<void> _showPlaylistFormSheet({
    required String title,
    required String submitLabel,
    required Future<void> Function(String title, String? description) onSubmit,
    String initialTitle = '',
    String? initialDescription,
  }) async {
    final titleController = TextEditingController(text: initialTitle);
    final descriptionController = TextEditingController(
      text: initialDescription ?? '',
    );

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        var isSaving = false;
        return StatefulBuilder(
          builder: (ctx, setSheetState) {
            Future<void> submit() async {
              final playlistTitle = titleController.text.trim();
              if (playlistTitle.isEmpty || isSaving) return;

              setSheetState(() => isSaving = true);
              await onSubmit(
                playlistTitle,
                descriptionController.text.trim().isEmpty
                    ? null
                    : descriptionController.text.trim(),
              );
              if (!ctx.mounted) return;
              Navigator.pop(ctx);
            }

            return Padding(
              padding: EdgeInsets.only(
                left: 10,
                right: 10,
                bottom: MediaQuery.viewInsetsOf(ctx).bottom + 10,
              ),
              child: SafeArea(
                top: false,
                child: Container(
                  padding: const EdgeInsets.fromLTRB(18, 18, 18, 14),
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(
                      color: AppTheme.ink.withValues(alpha: 0.08),
                    ),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        title,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 16),
                      _DarkTextField(
                        controller: titleController,
                        placeholder: 'Title',
                        autofocus: true,
                      ),
                      const SizedBox(height: 10),
                      _DarkTextField(
                        controller: descriptionController,
                        placeholder: 'Description',
                      ),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(
                            child: _SheetButton(
                              label: 'Cancel',
                              onTap: () => Navigator.pop(ctx),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: _SheetButton(
                              label: submitLabel,
                              highlighted: true,
                              isLoading: isSaving,
                              onTap: submit,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            );
          },
        );
      },
    );

    titleController.dispose();
    descriptionController.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.appBackground,
      body: BlocBuilder<LibraryCubit, LibraryState>(
        builder: (context, state) {
          return Stack(
            children: [
              CustomScrollView(
                physics: const BouncingScrollPhysics(),
                slivers: [
                  SliverToBoxAdapter(
                    child: SizedBox(
                      height: MediaQuery.paddingOf(context).top + 78,
                    ),
                  ),
                  if (state is LibraryLoading)
                    const SliverFillRemaining(
                      child: OmniLoadingState(message: 'Loading library'),
                    )
                  else if (state is LibraryLoaded) ...[
                    SliverPadding(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      sliver: SliverList(
                        delegate: SliverChildListDelegate([
                          _buildFavoritesTile(state.favorites),
                          const SizedBox(height: 26),
                          _buildPlaylistsHeader(state.playlists),
                          const SizedBox(height: 10),
                          if (_isPlaylistEditMode)
                            _buildPlaylistEditBar(state.playlists),
                          if (_isPlaylistEditMode) const SizedBox(height: 10),
                          if (state.playlists.isEmpty)
                            _buildEmptyPlaylists()
                          else
                            ...state.playlists.map(
                              (playlist) => _buildPlaylistTile(
                                playlist: playlist,
                                items:
                                    state.playlistItemsById[playlist.id] ??
                                    const [],
                              ),
                            ),
                        ]),
                      ),
                    ),
                    const SliverToBoxAdapter(
                      child: Padding(
                        padding: EdgeInsets.fromLTRB(20, 30, 20, 16),
                        child: Text(
                          'Recently Added',
                          style: TextStyle(
                            fontSize: 21,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                    ..._buildRecentlyAddedSlivers(state.favorites),
                  ] else if (state is LibraryError)
                    SliverFillRemaining(
                      hasScrollBody: false,
                      child: OmniErrorState(
                        message: state.message,
                        onRetry: () => context
                            .read<LibraryCubit>()
                            .loadLibraryData(force: true),
                      ),
                    ),
                  const SliverToBoxAdapter(child: SizedBox(height: 110)),
                ],
              ),
              Positioned(
                top: 0,
                left: 0,
                right: 0,
                child: _buildAppBar(context),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildAppBar(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            AppTheme.appBackground.withValues(alpha: 0.98),
            AppTheme.appBackground.withValues(alpha: 0.86),
            AppTheme.appBackground.withValues(alpha: 0),
          ],
        ),
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 10),
          child: Row(
            children: [
              const Text(
                'Library',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w600,
                  height: 1.12,
                ),
              ),
              const Spacer(),
              _ToolbarCluster(
                children: [
                  _ToolbarIcon(
                    icon: CupertinoIcons.plus,
                    onTap: _showCreatePlaylistSheet,
                  ),
                  _ToolbarIcon(
                    icon: CupertinoIcons.chart_bar_alt_fill,
                    onTap: () => Navigator.push(
                      context,
                      CupertinoPageRoute(
                        builder: (_) => const SmartLibraryScreen(),
                      ),
                    ),
                  ),
                  _ToolbarIcon(
                    icon: _isPlaylistEditMode
                        ? CupertinoIcons.check_mark
                        : CupertinoIcons.line_horizontal_3_decrease,
                    onTap: _togglePlaylistEditor,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _buildRecentlyAddedSlivers(List<UnifiedContent> items) {
    if (items.isEmpty) {
      return [
        SliverToBoxAdapter(
          child: SizedBox(
            height: 230,
            child: OmniEmptyState(
              icon: PhosphorIcons.heart(PhosphorIconsStyle.light),
              title: 'No favorites yet',
              subtitle: 'Liked movies, songs, and books will appear here.',
            ),
          ),
        ),
      ];
    }

    final clusters = groupMusicAlbums(items);
    final visibleCount = clusters.length < _recentVisibleCount
        ? clusters.length
        : _recentVisibleCount;
    final canShowMore = visibleCount < clusters.length;

    return [
      SliverPadding(
        padding: const EdgeInsets.symmetric(horizontal: 20),
        sliver: SliverGrid(
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            mainAxisSpacing: 15,
            crossAxisSpacing: 15,
            childAspectRatio: 0.54,
          ),
          delegate: SliverChildBuilderDelegate((context, index) {
            final cluster = clusters[index];
            return ContentCard(
              item: cluster.primary,
              groupedItems: cluster.items,
            );
          }, childCount: visibleCount),
        ),
      ),
      if (clusters.length > _recentPageSize)
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 18, 20, 0),
            child: Center(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () {
                  setState(() {
                    if (canShowMore) {
                      final next = _recentVisibleCount + _recentPageSize;
                      _recentVisibleCount = next > clusters.length
                          ? clusters.length
                          : next;
                    } else {
                      _recentVisibleCount = _recentPageSize;
                    }
                  });
                },
                child: Container(
                  height: 40,
                  padding: const EdgeInsets.symmetric(horizontal: 18),
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(
                      color: AppTheme.ink.withValues(alpha: 0.08),
                    ),
                  ),
                  child: Text(
                    canShowMore ? 'See more' : 'Show less',
                    style: const TextStyle(
                      color: AppTheme.primary,
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
    ];
  }

  Widget _buildFavoritesTile(List<UnifiedContent> favorites) {
    return _LibraryRow(
      title: 'Favorites',
      subtitle: '${favorites.length} items',
      icon: CupertinoIcons.heart_fill,
      iconColor: const Color(0xFFFF5D73),
      onTap: () => Navigator.push(
        context,
        CupertinoPageRoute(
          builder: (_) => PlaylistDetailScreen(
            title: 'Favorites',
            initialItems: favorites,
            isFavorites: true,
          ),
        ),
      ),
    );
  }

  Widget _buildPlaylistsHeader(List<PlaylistModel> playlists) {
    return Row(
      children: [
        const Text(
          'Playlists',
          style: TextStyle(fontSize: 21, fontWeight: FontWeight.w600),
        ),
        const Spacer(),
        if (_isPlaylistEditMode)
          Text(
            '${_selectedPlaylistIds.length} selected',
            style: TextStyle(
              color: AppTheme.ink.withValues(alpha: 0.52),
              fontSize: 13,
            ),
          )
        else
          Text(
            '${playlists.length}',
            style: TextStyle(
              color: AppTheme.ink.withValues(alpha: 0.52),
              fontSize: 13,
            ),
          ),
      ],
    );
  }

  Widget _buildPlaylistEditBar(List<PlaylistModel> playlists) {
    final hasSelection = _selectedPlaylistIds.isNotEmpty;
    final canRename = _selectedPlaylistIds.length == 1;
    final allSelected =
        playlists.isNotEmpty && _selectedPlaylistIds.length == playlists.length;

    return Row(
      children: [
        _InlineActionButton(
          label: allSelected ? 'Deselect' : 'Select all',
          onTap: playlists.isEmpty
              ? null
              : () => _selectAllPlaylists(playlists),
        ),
        const SizedBox(width: 8),
        _InlineActionButton(
          label: 'Rename',
          onTap: canRename ? () => _renameSelectedPlaylist(playlists) : null,
        ),
        const SizedBox(width: 8),
        _InlineActionButton(
          label: _isDeletingPlaylists ? 'Deleting' : 'Delete',
          destructive: true,
          onTap: hasSelection ? _deleteSelectedPlaylists : null,
        ),
      ],
    );
  }

  Widget _buildEmptyPlaylists() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 18),
      child: Text(
        'No playlists yet',
        style: TextStyle(color: AppTheme.ink.withValues(alpha: 0.46)),
      ),
    );
  }

  Widget _buildPlaylistTile({
    required PlaylistModel playlist,
    required List<UnifiedContent> items,
  }) {
    final isSelected = _selectedPlaylistIds.contains(playlist.id);
    return _LibraryRow(
      title: playlist.title,
      subtitle: playlist.description?.trim().isNotEmpty == true
          ? '${items.length} items - ${playlist.description!.trim()}'
          : '${items.length} items',
      imageUrl: items.isNotEmpty ? items.first.imageUrl : null,
      icon: CupertinoIcons.music_note_list,
      selectable: _isPlaylistEditMode,
      selected: isSelected,
      onTap: () {
        if (_isPlaylistEditMode) {
          _togglePlaylistSelection(playlist.id);
          return;
        }
        Navigator.push(
          context,
          CupertinoPageRoute(
            builder: (_) => PlaylistDetailScreen(
              playlistId: playlist.id,
              title: playlist.title,
              description: playlist.description,
              initialItems: items,
            ),
          ),
        );
      },
    );
  }
}

class _ToolbarCluster extends StatelessWidget {
  final List<Widget> children;

  const _ToolbarCluster({required this.children});

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 42,
      padding: const EdgeInsets.symmetric(horizontal: 4),
      decoration: BoxDecoration(
        color: AppTheme.surface.withValues(alpha: 0.86),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppTheme.ink.withValues(alpha: 0.08)),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: children),
    );
  }
}

class _ToolbarIcon extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;

  const _ToolbarIcon({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: SizedBox(
        width: 38,
        height: 38,
        child: Icon(icon, size: 23, color: AppTheme.ink),
      ),
    );
  }
}

class _LibraryRow extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final Color? iconColor;
  final String? imageUrl;
  final bool selectable;
  final bool selected;
  final VoidCallback onTap;

  const _LibraryRow({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.onTap,
    this.iconColor,
    this.imageUrl,
    this.selectable = false,
    this.selected = false,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 9),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(color: AppTheme.ink.withValues(alpha: 0.08)),
          ),
        ),
        child: Row(
          children: [
            if (selectable) ...[
              Icon(
                selected
                    ? CupertinoIcons.check_mark_circled_solid
                    : CupertinoIcons.circle,
                color: selected
                    ? AppTheme.primary
                    : AppTheme.ink.withValues(alpha: 0.42),
                size: 24,
              ),
              const SizedBox(width: 12),
            ],
            _LibraryArtwork(
              imageUrl: imageUrl,
              icon: icon,
              iconColor: iconColor,
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    subtitle,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: AppTheme.ink.withValues(alpha: 0.52),
                      fontSize: 14,
                    ),
                  ),
                ],
              ),
            ),
            if (!selectable)
              Icon(
                CupertinoIcons.chevron_right,
                color: AppTheme.ink.withValues(alpha: 0.42),
                size: 18,
              ),
          ],
        ),
      ),
    );
  }
}

class _LibraryArtwork extends StatelessWidget {
  final String? imageUrl;
  final IconData icon;
  final Color? iconColor;

  const _LibraryArtwork({
    required this.imageUrl,
    required this.icon,
    this.iconColor,
  });

  @override
  Widget build(BuildContext context) {
    final url = (imageUrl ?? '').trim();

    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: SizedBox(
        width: 58,
        height: 58,
        child: url.isNotEmpty
            ? Image.network(
                url,
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) => _fallback(),
              )
            : _fallback(),
      ),
    );
  }

  Widget _fallback() {
    return Container(
      color: AppTheme.surfaceAlt,
      alignment: Alignment.center,
      child: Icon(
        icon,
        color: iconColor ?? AppTheme.ink.withValues(alpha: 0.62),
        size: 24,
      ),
    );
  }
}

class _InlineActionButton extends StatelessWidget {
  final String label;
  final VoidCallback? onTap;
  final bool destructive;

  const _InlineActionButton({
    required this.label,
    required this.onTap,
    this.destructive = false,
  });

  @override
  Widget build(BuildContext context) {
    final enabled = onTap != null;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: AnimatedOpacity(
        duration: const Duration(milliseconds: 150),
        opacity: enabled ? 1 : 0.38,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 8),
          decoration: BoxDecoration(
            color: AppTheme.surface.withValues(alpha: 0.9),
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: AppTheme.ink.withValues(alpha: 0.08)),
          ),
          child: Text(
            label,
            style: TextStyle(
              color: destructive ? const Color(0xFFFF6B7A) : AppTheme.ink,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ),
    );
  }
}

class _DarkTextField extends StatelessWidget {
  final TextEditingController controller;
  final String placeholder;
  final bool autofocus;

  const _DarkTextField({
    required this.controller,
    required this.placeholder,
    this.autofocus = false,
  });

  @override
  Widget build(BuildContext context) {
    return CupertinoTextField(
      controller: controller,
      autofocus: autofocus,
      cursorColor: AppTheme.primary,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
      placeholder: placeholder,
      placeholderStyle: TextStyle(color: AppTheme.ink.withValues(alpha: 0.38)),
      style: const TextStyle(color: AppTheme.ink, fontSize: 16),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.38),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.ink.withValues(alpha: 0.08)),
      ),
    );
  }
}

class _SheetButton extends StatelessWidget {
  final String label;
  final bool highlighted;
  final bool isLoading;
  final VoidCallback onTap;

  const _SheetButton({
    required this.label,
    required this.onTap,
    this.highlighted = false,
    this.isLoading = false,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: isLoading ? null : onTap,
      child: Container(
        height: 46,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: highlighted
              ? AppTheme.primary
              : AppTheme.ink.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(14),
        ),
        child: isLoading
            ? const CupertinoActivityIndicator(color: Colors.white)
            : Text(
                label,
                style: TextStyle(
                  color: highlighted ? Colors.white : AppTheme.ink,
                  fontWeight: FontWeight.w600,
                ),
              ),
      ),
    );
  }
}
