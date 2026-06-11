import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/utils/content_display.dart';
import '../../../domain/entities/unified_content.dart';
import '../../../domain/repositories/content_repository.dart';
import '../../widgets/minimal_page_header.dart';
import '../search/search_grid_card.dart';

class CollectionsScreen extends StatefulWidget {
  const CollectionsScreen({super.key});

  @override
  State<CollectionsScreen> createState() => _CollectionsScreenState();
}

class _CollectionsScreenState extends State<CollectionsScreen> {
  static const _collections = [
    _CollectionConfig(
      title: 'Cyber Mood',
      tags: ['cyberpunk', 'noir'],
      type: 'movie',
      colors: [Color(0xFF2DD4BF), Color(0xFF2563EB)],
    ),
    _CollectionConfig(
      title: 'Late Night',
      tags: ['chill', 'dark'],
      type: 'music',
      colors: [Color(0xFF1D4ED8), Color(0xFF06B6D4)],
    ),
    _CollectionConfig(
      title: 'Mind Benders',
      tags: ['mystery', 'mind-bending'],
      type: 'all',
      colors: [Color(0xFF0F766E), Color(0xFFEAB308)],
    ),
    _CollectionConfig(
      title: 'Epic Worlds',
      tags: ['fantasy', 'epic'],
      type: 'book',
      colors: [Color(0xFF22C55E), Color(0xFF84CC16)],
    ),
  ];

  final Map<String, List<UnifiedContent>> _itemsByCollection = {};
  bool _loading = true;
  String _error = '';
  String _activeType = 'all';

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
            (tag) => repo.getDeepResearch(
              tag,
              type: collection.type == 'all' ? null : collection.type,
            ),
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
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final visible = _collections.where((collection) {
      return _activeType == 'all' ||
          collection.type == _activeType ||
          collection.type == 'all';
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
              ),
            ),
            SliverToBoxAdapter(
              child: SubtleCountText(
                text: _loading
                    ? 'Curating collections...'
                    : '${visible.length} collections built from moods and genres.',
              ),
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 22)),
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
                padding: const EdgeInsets.fromLTRB(24, 0, 24, 104),
                sliver: SliverGrid(
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    crossAxisSpacing: 16,
                    mainAxisSpacing: 16,
                    childAspectRatio: 0.92,
                  ),
                  delegate: SliverChildBuilderDelegate((context, index) {
                    final collection = visible[index];
                    final items =
                        _itemsByCollection[collection.title] ??
                        const <UnifiedContent>[];
                    return _CollectionTile(
                      collection: collection,
                      itemCount: items.length,
                      onTap: () {
                        Navigator.push(
                          context,
                          CupertinoPageRoute(
                            builder: (_) => _CollectionDetailScreen(
                              collection: collection,
                              items: items,
                            ),
                          ),
                        );
                      },
                    );
                  }, childCount: visible.length),
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
  final int itemCount;
  final VoidCallback onTap;

  const _CollectionTile({
    required this.collection,
    required this.itemCount,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(24),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: collection.colors,
          ),
        ),
        child: Stack(
          children: [
            Positioned(
              right: -22,
              top: -18,
              child: Container(
                width: 108,
                height: 108,
                decoration: BoxDecoration(
                  color: AppTheme.ink.withValues(alpha: 0.15),
                  shape: BoxShape.circle,
                ),
              ),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  collection.type == 'all'
                      ? 'MIXED'
                      : collection.type.toUpperCase(),
                  style: TextStyle(
                    color: AppTheme.ink.withValues(alpha: 0.68),
                    fontSize: 11,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const Spacer(),
                Text(
                  collection.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.ink,
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    height: 1.08,
                  ),
                ),
                const SizedBox(height: 7),
                Text(
                  '${collection.tags.join(', ')}  $itemCount picks',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: AppTheme.ink.withValues(alpha: 0.72),
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
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
  final List<Color> colors;

  const _CollectionConfig({
    required this.title,
    required this.tags,
    required this.type,
    required this.colors,
  });
}
