import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/utils/content_display.dart';
import '../../../domain/entities/unified_content.dart';
import '../../../domain/repositories/content_repository.dart';
import '../../bloc/home/home_cubit.dart';
import '../../bloc/library/library_cubit.dart';
import '../../widgets/app_feedback.dart';
import '../../widgets/minimal_page_header.dart';
import '../search/search_grid_card.dart';

class ForYouHubScreen extends StatefulWidget {
  const ForYouHubScreen({super.key});

  @override
  State<ForYouHubScreen> createState() => _ForYouHubScreenState();
}

class _ForYouHubScreenState extends State<ForYouHubScreen> {
  String _activeType = 'music';
  bool _isLoading = true;
  String _error = '';
  List<UnifiedContent> _items = const [];

  @override
  void initState() {
    super.initState();
    context.read<LibraryCubit>().loadLibraryData(showLoader: false);
    _hydrateFromHome();
    _load(silent: _items.isNotEmpty);
  }

  void _hydrateFromHome() {
    final homeState = context.read<HomeCubit>().state;
    _activeType = _typeForCategory(homeState.category);
    if (homeState.recommendations.isEmpty) return;
    setState(() {
      _items = homeState.recommendations;
      _isLoading = false;
    });
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

  Future<void> _load({bool silent = false}) async {
    if (!silent || _items.isEmpty) {
      setState(() {
        _isLoading = true;
        _error = '';
      });
    } else {
      setState(() => _error = '');
    }

    try {
      final repo = context.read<ContentRepository>();
      final type = _activeType == 'all' ? null : _activeType;
      final recommendations = await repo.getRecommendations(type: type);
      if (!mounted) return;
      setState(() => _items = recommendations);
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Failed to load recommendations');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _setType(String type) {
    if (_activeType == type) return;
    setState(() {
      _activeType = type;
      _items = const [];
    });
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final displayItems = groupMusicAlbums(_items);

    return Scaffold(
      backgroundColor: AppTheme.appBackground,
      body: RefreshIndicator(
        backgroundColor: AppTheme.surface,
        color: AppTheme.ink,
        onRefresh: () => _load(),
        child: CustomScrollView(
          physics: const BouncingScrollPhysics(
            parent: AlwaysScrollableScrollPhysics(),
          ),
          slivers: [
            const SliverToBoxAdapter(
              child: MinimalPageHeader(title: 'For you'),
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
                text: displayItems.isEmpty
                    ? 'Personalized picks will appear here.'
                    : '${displayItems.length} curated picks based on your taste.',
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
                  icon: PhosphorIcons.sparkle(PhosphorIconsStyle.light),
                  title: 'No picks yet',
                  subtitle: 'Try another type or pull to refresh the feed.',
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
