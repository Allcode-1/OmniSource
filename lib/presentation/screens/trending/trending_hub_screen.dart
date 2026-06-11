import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/utils/content_display.dart';
import '../../../domain/entities/unified_content.dart';
import '../../../domain/repositories/content_repository.dart';
import '../../bloc/home/home_cubit.dart';
import '../../widgets/app_feedback.dart';
import '../../widgets/minimal_page_header.dart';
import '../search/search_grid_card.dart';

class TrendingHubScreen extends StatefulWidget {
  const TrendingHubScreen({super.key});

  @override
  State<TrendingHubScreen> createState() => _TrendingHubScreenState();
}

class _TrendingHubScreenState extends State<TrendingHubScreen> {
  String _activeType = 'music';
  final Map<String, List<UnifiedContent>> _cache = {};
  bool _isLoading = true;
  String _error = '';

  @override
  void initState() {
    super.initState();
    final homeState = context.read<HomeCubit>().state;
    _activeType = _typeForCategory(homeState.category);
    if (homeState.trending.isNotEmpty) {
      _cache[_activeType] = homeState.trending;
      _isLoading = false;
    }
    _load(silent: _cache.isNotEmpty);
  }

  String _typeForCategory(ContentCategory category) {
    switch (category) {
      case ContentCategory.all:
        return 'music';
      case ContentCategory.movie:
        return 'movie';
      case ContentCategory.music:
        return 'music';
      case ContentCategory.book:
        return 'book';
    }
  }

  Future<void> _load({bool silent = false, bool force = false}) async {
    if (!force && _cache.containsKey(_activeType)) {
      setState(() {
        _error = '';
        _isLoading = false;
      });
      return;
    }

    if (!silent || _cache.isEmpty) {
      setState(() {
        _isLoading = true;
        _error = '';
      });
    } else {
      setState(() => _error = '');
    }

    try {
      final repo = context.read<ContentRepository>();
      final data = await repo.getTrending(
        type: _activeType == 'all' ? null : _activeType,
      );
      if (!mounted) return;
      setState(() => _cache[_activeType] = data);
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Failed to load trending feed');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _setType(String type) {
    if (_activeType == type) return;
    setState(() => _activeType = type);
    _load(silent: _cache.isNotEmpty);
  }

  @override
  Widget build(BuildContext context) {
    final items = _cache[_activeType] ?? const <UnifiedContent>[];
    final displayItems = groupMusicAlbums(items);

    return Scaffold(
      backgroundColor: AppTheme.appBackground,
      body: RefreshIndicator(
        backgroundColor: AppTheme.surface,
        color: AppTheme.ink,
        onRefresh: () => _load(force: true),
        child: CustomScrollView(
          physics: const BouncingScrollPhysics(
            parent: AlwaysScrollableScrollPhysics(),
          ),
          slivers: [
            const SliverToBoxAdapter(
              child: MinimalPageHeader(title: 'Trending'),
            ),
            SliverToBoxAdapter(
              child: MinimalTypeTabs(
                activeType: _activeType,
                onChanged: _setType,
                includeAll: false,
              ),
            ),
            SliverToBoxAdapter(
              child: SubtleCountText(
                text: items.isEmpty
                    ? 'Trending picks will appear here.'
                    : '${displayItems.length} active picks in this stream.',
              ),
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 22)),
            if (_isLoading && displayItems.isEmpty)
              const OmniGridSkeletonSliver(
                padding: EdgeInsets.fromLTRB(24, 0, 24, 104),
              )
            else if (_error.isNotEmpty && displayItems.isEmpty)
              SliverFillRemaining(
                hasScrollBody: false,
                child: OmniErrorState(message: _error, onRetry: () => _load()),
              )
            else if (displayItems.isEmpty)
              SliverFillRemaining(
                hasScrollBody: false,
                child: OmniEmptyState(
                  icon: PhosphorIcons.trendUp(PhosphorIconsStyle.light),
                  title: 'Nothing trending yet',
                  subtitle: 'Pull to refresh or switch the content type.',
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
                    childAspectRatio: contentGridAspectRatio(_activeType),
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
      ),
    );
  }
}
