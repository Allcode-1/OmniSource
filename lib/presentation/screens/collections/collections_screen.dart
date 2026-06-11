import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/utils/content_display.dart';
import '../../../domain/entities/unified_content.dart';
import '../../../domain/repositories/content_repository.dart';
import '../../widgets/content_artwork.dart';
import '../../widgets/minimal_page_header.dart';
import '../search/search_grid_card.dart';

class CollectionsScreen extends StatefulWidget {
  final String? initialCollectionTitle;

  const CollectionsScreen({super.key, this.initialCollectionTitle});

  @override
  State<CollectionsScreen> createState() => _CollectionsScreenState();
}

class _CollectionsScreenState extends State<CollectionsScreen> {
  static const _collections = [
    _CollectionConfig(
      title: 'Cyber Mood',
      tags: ['cyberpunk', 'noir'],
      type: 'movie',
      icon: CupertinoIcons.moon_stars_fill,
    ),
    _CollectionConfig(
      title: 'Late Night',
      tags: ['chill', 'dark'],
      type: 'music',
      icon: CupertinoIcons.music_note_2,
    ),
    _CollectionConfig(
      title: 'Mind Benders',
      tags: ['mystery', 'psychological', 'surreal'],
      type: 'movie',
      icon: CupertinoIcons.sparkles,
    ),
    _CollectionConfig(
      title: 'Epic Worlds',
      tags: ['fantasy', 'epic'],
      type: 'book',
      icon: CupertinoIcons.book_fill,
    ),
  ];

  final Map<String, List<UnifiedContent>> _itemsByCollection = {};
  bool _loading = true;
  bool _openedInitial = false;
  String _error = '';
  String _activeType = 'movie';

  String _contentKey(UnifiedContent item) => '${item.type}:${item.externalId}';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = '';
    });

    try {
      final repo = context.read<ContentRepository>();
      for (final collection in _collections) {
        final responses = await Future.wait(
          collection.tags.map(
            (tag) => repo.getDeepResearch(tag, type: collection.type),
          ),
        );

        final map = <String, UnifiedContent>{};
        for (final list in responses) {
          for (final item in list) {
            map[_contentKey(item)] = item;
          }
        }
        _itemsByCollection[collection.title] = map.values.take(24).toList();
      }
    } catch (_) {
      _error = 'Failed to load collections';
    } finally {
      if (mounted) {
        setState(() => _loading = false);
        _openInitialCollectionIfNeeded();
      }
    }
  }

  void _openInitialCollectionIfNeeded() {
    final initialTitle = widget.initialCollectionTitle;
    if (_openedInitial || initialTitle == null || _error.isNotEmpty) return;
    final collection = _collections.where((item) => item.title == initialTitle);
    if (collection.isEmpty) return;
    _openedInitial = true;

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _openCollection(collection.first);
    });
  }

  void _openCollection(_CollectionConfig collection) {
    final items =
        _itemsByCollection[collection.title] ?? const <UnifiedContent>[];
    Navigator.push(
      context,
      CupertinoPageRoute(
        builder: (_) =>
            _CollectionDetailScreen(collection: collection, items: items),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final visible = _collections.where((collection) {
      return collection.type == _activeType;
    }).toList();

    return Scaffold(
      backgroundColor: AppTheme.appBackground,
      body: RefreshIndicator(
        backgroundColor: AppTheme.surface,
        color: AppTheme.ink,
        onRefresh: _load,
        child: CustomScrollView(
          physics: const BouncingScrollPhysics(
            parent: AlwaysScrollableScrollPhysics(),
          ),
          slivers: [
            const SliverToBoxAdapter(
              child: MinimalPageHeader(title: 'Collections'),
            ),
            SliverToBoxAdapter(
              child: MinimalTypeTabs(
                activeType: _activeType,
                onChanged: (type) => setState(() => _activeType = type),
                includeAll: false,
              ),
            ),
            SliverToBoxAdapter(
              child: SubtleCountText(
                text: _loading
                    ? 'Curating collections...'
                    : '${visible.length} collections built from moods and genres.',
              ),
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 18)),
            if (_loading)
              const SliverFillRemaining(
                child: Center(child: CupertinoActivityIndicator()),
              )
            else if (_error.isNotEmpty)
              SliverFillRemaining(
                hasScrollBody: false,
                child: Center(
                  child: Text(
                    _error,
                    style: const TextStyle(color: Color(0xFFFF7A7A)),
                  ),
                ),
              )
            else
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 104),
                sliver: SliverList.separated(
                  itemCount: visible.length,
                  separatorBuilder: (context, index) =>
                      const SizedBox(height: 12),
                  itemBuilder: (context, index) {
                    final collection = visible[index];
                    final items =
                        _itemsByCollection[collection.title] ??
                        const <UnifiedContent>[];
                    return _CollectionTile(
                      collection: collection,
                      items: items,
                      onTap: () => _openCollection(collection),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _CollectionTile extends StatelessWidget {
  final _CollectionConfig collection;
  final List<UnifiedContent> items;
  final VoidCallback onTap;

  const _CollectionTile({
    required this.collection,
    required this.items,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Container(
        constraints: const BoxConstraints(minHeight: 120),
        padding: const EdgeInsets.fromLTRB(16, 15, 16, 15),
        decoration: BoxDecoration(
          color: AppTheme.surfaceAlt,
          borderRadius: BorderRadius.circular(22),
        ),
        child: Row(
          children: [
            _CollectionArtworkStack(
              items: items,
              fallbackIcon: collection.icon,
              size: 88,
            ),
            const SizedBox(width: 15),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    collection.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppTheme.ink,
                      fontSize: 20,
                      fontWeight: FontWeight.w600,
                      height: 1.1,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    collection.tags.join(', '),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: AppTheme.ink.withValues(alpha: 0.54),
                      fontSize: 14,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '${_collectionTypeLabel(collection.type)} - ${items.length} picks',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: AppTheme.ink.withValues(alpha: 0.38),
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),
            Icon(
              CupertinoIcons.chevron_right,
              color: AppTheme.ink.withValues(alpha: 0.28),
              size: 18,
            ),
          ],
        ),
      ),
    );
  }
}

class _CollectionArtworkStack extends StatelessWidget {
  final List<UnifiedContent> items;
  final IconData fallbackIcon;
  final double size;

  const _CollectionArtworkStack({
    required this.items,
    required this.fallbackIcon,
    required this.size,
  });

  @override
  Widget build(BuildContext context) {
    final artItems = items.take(3).toList(growable: false);
    if (artItems.isEmpty) {
      return Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppTheme.ink.withValues(alpha: 0.06)),
        ),
        child: Icon(fallbackIcon, color: AppTheme.primary, size: size * 0.36),
      );
    }

    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          for (var index = artItems.length - 1; index >= 0; index--)
            Positioned(
              left: index * (size * 0.17),
              top: index * (size * 0.08),
              child: Container(
                width: size * 0.72,
                height: size * 0.72,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(14),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.2),
                      blurRadius: 10,
                      offset: const Offset(0, 5),
                    ),
                  ],
                ),
                child: ContentArtwork(
                  item: artItems[index],
                  borderRadius: 14,
                  memCacheWidth: 220,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

String _collectionTypeLabel(String type) {
  return contentTypeLabel(type);
}

class _CollectionDetailScreen extends StatelessWidget {
  final _CollectionConfig collection;
  final List<UnifiedContent> items;

  const _CollectionDetailScreen({
    required this.collection,
    required this.items,
  });

  @override
  Widget build(BuildContext context) {
    final displayItems = groupMusicAlbums(items);

    return Scaffold(
      backgroundColor: AppTheme.appBackground,
      body: CustomScrollView(
        physics: const BouncingScrollPhysics(),
        slivers: [
          SliverToBoxAdapter(child: MinimalPageHeader(title: collection.title)),
          SliverToBoxAdapter(
            child: SubtleCountText(
              text:
                  '${displayItems.length} picks from ${collection.tags.join(', ')}.',
            ),
          ),
          const SliverToBoxAdapter(child: SizedBox(height: 22)),
          if (displayItems.isEmpty)
            const SliverFillRemaining(
              hasScrollBody: false,
              child: Center(
                child: Text(
                  'No items in this collection yet',
                  style: TextStyle(color: Colors.white54),
                ),
              ),
            )
          else
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 104),
              sliver: SliverGrid(
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  crossAxisSpacing: 16,
                  mainAxisSpacing: 18,
                  childAspectRatio: contentGridAspectRatio(collection.type),
                ),
                delegate: SliverChildBuilderDelegate((context, index) {
                  final cluster = displayItems[index];
                  return SearchGridCard(
                    item: cluster.primary,
                    groupedItems: cluster.items,
                  );
                }, childCount: displayItems.length),
              ),
            ),
        ],
      ),
    );
  }
}

class _CollectionConfig {
  final String title;
  final List<String> tags;
  final String type;
  final IconData icon;

  const _CollectionConfig({
    required this.title,
    required this.tags,
    required this.type,
    required this.icon,
  });
}
