import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/theme/app_theme.dart';
import '../../../domain/entities/unified_content.dart';
import '../../bloc/library/library_cubit.dart';
import '../../widgets/content_artwork.dart';
import '../home/detail_screen.dart';

class PlaylistDetailScreen extends StatefulWidget {
  final String? playlistId;
  final String title;
  final String? description;
  final List<UnifiedContent> initialItems;
  final bool isFavorites;

  const PlaylistDetailScreen({
    super.key,
    this.playlistId,
    required this.title,
    this.description,
    required this.initialItems,
    this.isFavorites = false,
  });

  @override
  State<PlaylistDetailScreen> createState() => _PlaylistDetailScreenState();
}

class _PlaylistDetailScreenState extends State<PlaylistDetailScreen> {
  bool isEditMode = false;
  Set<String> selectedIds = {};
  String filterType = 'all';
  bool sortNewest = true;
  bool _isRemoving = false;
  late List<UnifiedContent> _items;

  String _contentRef(UnifiedContent item) => '${item.type}:${item.externalId}';

  @override
  void initState() {
    super.initState();
    _items = List<UnifiedContent>.from(widget.initialItems);
  }

  Future<void> _removeSelected() async {
    if (selectedIds.isEmpty || _isRemoving) return;

    final cubit = context.read<LibraryCubit>();
    setState(() => _isRemoving = true);

    try {
      final ids = selectedIds.toList();
      if (widget.isFavorites) {
        final selectedItems = _items
            .where((item) => selectedIds.contains(_contentRef(item)))
            .toList();
        await cubit.removeFavorites(selectedItems);
      } else if (widget.playlistId != null) {
        await cubit.removeItemsFromPlaylist(widget.playlistId!, ids);
      }

      if (!mounted) return;
      setState(() {
        _items = _items
            .where((item) => !selectedIds.contains(_contentRef(item)))
            .toList();
        selectedIds.clear();
        isEditMode = false;
      });
    } finally {
      if (mounted) {
        setState(() => _isRemoving = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    List<UnifiedContent> filteredItems = _items.where((item) {
      if (filterType == 'all') return true;
      return item.type == filterType;
    }).toList();

    if (!sortNewest) filteredItems = filteredItems.reversed.toList();

    return Scaffold(
      backgroundColor: AppTheme.appBackground,
      body: CustomScrollView(
        physics: const BouncingScrollPhysics(),
        slivers: [
          SliverToBoxAdapter(child: _buildHeader()),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 14, 20, 0),
              child: _buildHero(),
            ),
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 22, 20, 0),
              child: _buildFilterRow(),
            ),
          ),
          if (isEditMode)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(20, 10, 20, 0),
                child: _buildEditTools(filteredItems),
              ),
            ),
          if (filteredItems.isEmpty)
            SliverFillRemaining(
              hasScrollBody: false,
              child: Center(
                child: Text(
                  'No items here yet',
                  style: TextStyle(
                    color: AppTheme.ink.withValues(alpha: 0.46),
                    fontSize: 15,
                  ),
                ),
              ),
            )
          else
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 110),
              sliver: SliverList(
                delegate: SliverChildBuilderDelegate((context, index) {
                  final item = filteredItems[index];
                  final isSelected = selectedIds.contains(_contentRef(item));
                  return _buildItemTile(item, isSelected);
                }, childCount: filteredItems.length),
              ),
            ),
        ],
      ),
      bottomSheet: isEditMode && selectedIds.isNotEmpty
          ? SafeArea(
              top: false,
              child: Container(
                color: AppTheme.surface.withValues(alpha: 0.98),
                padding: const EdgeInsets.fromLTRB(20, 12, 20, 14),
                child: SizedBox(
                  width: double.infinity,
                  height: 46,
                  child: FilledButton(
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xFFFF5D73),
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    onPressed: _isRemoving ? null : _removeSelected,
                    child: _isRemoving
                        ? const CupertinoActivityIndicator(color: Colors.white)
                        : Text('Remove Selected (${selectedIds.length})'),
                  ),
                ),
              ),
            )
          : null,
    );
  }

  Widget _buildHeader() {
    return SafeArea(
      bottom: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 8, 14, 4),
        child: Row(
          children: [
            _CircleIconButton(
              icon: CupertinoIcons.back,
              onTap: () => Navigator.maybePop(context),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                widget.title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            const SizedBox(width: 8),
            CupertinoButton(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              minimumSize: const Size(40, 40),
              onPressed: () => setState(() {
                isEditMode = !isEditMode;
                selectedIds.clear();
              }),
              child: Text(
                isEditMode ? 'Done' : 'Edit',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHero() {
    final stats = _getStats();
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        _PlaylistCover(items: _items, isFavorites: widget.isFavorites),
        const SizedBox(width: 16),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(bottom: 3),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  widget.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontSize: 28,
                    fontWeight: FontWeight.w700,
                    height: 1.06,
                  ),
                ),
                if (widget.description?.trim().isNotEmpty == true) ...[
                  const SizedBox(height: 7),
                  Text(
                    widget.description!.trim(),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: AppTheme.ink.withValues(alpha: 0.58),
                      fontSize: 14,
                    ),
                  ),
                ],
                const SizedBox(height: 8),
                Text(
                  '${_items.length} items - $stats',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: AppTheme.ink.withValues(alpha: 0.48),
                    fontSize: 13,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildFilterRow() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: [
          _PillTab(
            label: 'All',
            selected: filterType == 'all',
            onTap: () {
              setState(() => filterType = 'all');
            },
          ),
          _PillTab(
            label: 'Music',
            selected: filterType == 'music',
            onTap: () {
              setState(() => filterType = 'music');
            },
          ),
          _PillTab(
            label: 'Movies',
            selected: filterType == 'movie',
            onTap: () {
              setState(() => filterType = 'movie');
            },
          ),
          _PillTab(
            label: 'Books',
            selected: filterType == 'book',
            onTap: () {
              setState(() => filterType = 'book');
            },
          ),
          const SizedBox(width: 8),
          _CircleIconButton(
            icon: sortNewest
                ? CupertinoIcons.sort_down
                : CupertinoIcons.sort_up,
            onTap: () => setState(() => sortNewest = !sortNewest),
          ),
        ],
      ),
    );
  }

  Widget _buildEditTools(List<UnifiedContent> filteredItems) {
    final allSelected =
        filteredItems.isNotEmpty && selectedIds.length == filteredItems.length;
    return Row(
      children: [
        CupertinoButton(
          padding: EdgeInsets.zero,
          onPressed: () => setState(() {
            selectedIds = allSelected
                ? {}
                : filteredItems.map((item) => _contentRef(item)).toSet();
          }),
          child: Text(allSelected ? 'Deselect' : 'Select all'),
        ),
        const Spacer(),
        Text(
          '${selectedIds.length} selected',
          style: TextStyle(color: AppTheme.ink.withValues(alpha: 0.52)),
        ),
      ],
    );
  }

  Widget _buildItemTile(UnifiedContent item, bool isSelected) {
    final artAspect = ContentArtwork.aspectRatioFor(item.type);
    final artWidth = item.type == 'music'
        ? 58.0
        : (58.0 * artAspect).clamp(38.0, 58.0);
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: () {
        if (isEditMode) {
          setState(() {
            if (isSelected) {
              selectedIds.remove(_contentRef(item));
            } else {
              selectedIds.add(_contentRef(item));
            }
          });
          return;
        }
        Navigator.push(
          context,
          CupertinoPageRoute(builder: (_) => DetailScreen(content: item)),
        );
      },
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 9),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(color: AppTheme.ink.withValues(alpha: 0.08)),
          ),
        ),
        child: Row(
          children: [
            if (isEditMode) ...[
              Icon(
                isSelected
                    ? CupertinoIcons.check_mark_circled_solid
                    : CupertinoIcons.circle,
                color: isSelected
                    ? AppTheme.primary
                    : AppTheme.ink.withValues(alpha: 0.42),
              ),
              const SizedBox(width: 12),
            ],
            ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: SizedBox(
                width: artWidth,
                height: 58,
                child: ContentArtwork(
                  item: item,
                  borderRadius: 10,
                  memCacheWidth: 220,
                ),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontWeight: FontWeight.w600,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    _subtitle(item),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: AppTheme.ink.withValues(alpha: 0.52),
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
            if (!isEditMode)
              Icon(
                CupertinoIcons.chevron_right,
                color: AppTheme.ink.withValues(alpha: 0.38),
                size: 18,
              ),
          ],
        ),
      ),
    );
  }

  String _subtitle(UnifiedContent item) {
    final pieces = <String>[_typeLabel(item.type)];
    if (item.rating > 0) pieces.add(item.rating.toStringAsFixed(1));
    if ((item.subtitle ?? '').isNotEmpty) pieces.add(item.subtitle!);
    return pieces.join(' - ');
  }

  String _typeLabel(String type) {
    switch (type) {
      case 'movie':
        return 'Movie';
      case 'book':
        return 'Book';
      case 'music':
        return 'Music';
      default:
        return 'Content';
    }
  }

  String _getStats() {
    final music = _items.where((i) => i.type == 'music').length;
    final movie = _items.where((i) => i.type == 'movie').length;
    final book = _items.where((i) => i.type == 'book').length;
    return '$music music - $movie movies - $book books';
  }
}

class _PlaylistCover extends StatelessWidget {
  final List<UnifiedContent> items;
  final bool isFavorites;

  const _PlaylistCover({required this.items, required this.isFavorites});

  @override
  Widget build(BuildContext context) {
    final firstItem = items.isEmpty ? null : items.first;
    if (firstItem == null || firstItem.imageUrl?.trim().isEmpty != false) {
      return Container(
        width: 112,
        height: 112,
        decoration: BoxDecoration(
          color: AppTheme.surfaceAlt,
          borderRadius: BorderRadius.circular(18),
        ),
        child: Icon(
          isFavorites ? CupertinoIcons.heart_fill : CupertinoIcons.music_note,
          color: isFavorites
              ? const Color(0xFFFF5D73)
              : AppTheme.ink.withValues(alpha: 0.42),
          size: 42,
        ),
      );
    }

    final artAspect = ContentArtwork.aspectRatioFor(firstItem.type);
    final artWidth = firstItem.type == 'music'
        ? 104.0
        : (104.0 * artAspect).clamp(68.0, 104.0);

    return Container(
      width: 112,
      height: 112,
      decoration: BoxDecoration(
        color: AppTheme.surfaceAlt,
        borderRadius: BorderRadius.circular(18),
      ),
      alignment: Alignment.center,
      child: SizedBox(
        width: artWidth,
        height: 104,
        child: ContentArtwork(
          item: firstItem,
          borderRadius: 14,
          memCacheWidth: 320,
        ),
      ),
    );
  }
}

class _PillTab extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _PillTab({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(right: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: selected
              ? AppTheme.primary
              : AppTheme.surface.withValues(alpha: 0.84),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Text(
          label,
          style: const TextStyle(
            color: AppTheme.ink,
            fontWeight: FontWeight.w600,
            fontSize: 13,
          ),
        ),
      ),
    );
  }
}

class _CircleIconButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;

  const _CircleIconButton({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        width: 40,
        height: 40,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppTheme.surface.withValues(alpha: 0.82),
          shape: BoxShape.circle,
          border: Border.all(color: AppTheme.ink.withValues(alpha: 0.08)),
        ),
        child: Icon(icon, color: AppTheme.ink, size: 22),
      ),
    );
  }
}
