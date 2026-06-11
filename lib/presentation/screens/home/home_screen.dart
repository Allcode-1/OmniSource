import 'dart:ui';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/utils/content_display.dart';
import '../../../domain/entities/unified_content.dart';
import '../../../domain/repositories/analytics_repository.dart';
import '../../../domain/repositories/user_repository.dart';
import '../../bloc/auth/auth_cubit.dart';
import '../../bloc/auth/auth_state.dart';
import '../../bloc/home/home_cubit.dart';
import '../../bloc/library/library_cubit.dart';
import '../../bloc/library/library_state.dart';
import '../../widgets/app_feedback.dart';
import '../../widgets/content_artwork.dart';
import '../../widgets/content_quick_actions.dart';
import '../../widgets/omni_cached_image.dart';
import '../../widgets/user_avatar.dart';
import '../calendar/release_calendar_screen.dart';
import '../collections/collections_screen.dart';
import '../profile/profile_screen.dart';
import '../trending/trending_hub_screen.dart';
import 'detail_screen.dart';
import 'for_you_hub_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  static const _accent = AppTheme.primary;
  static const _text = AppTheme.ink;
  static const _horizontalPadding = 20.0;
  static const _tabHorizontalPadding = 40.0;
  final ScrollController _scrollController = ScrollController();
  String _lastPrecacheSignature = '';
  double _appBarOpacity = 1.0;

  @override
  void initState() {
    super.initState();
    context.read<LibraryCubit>().loadLibraryData(showLoader: false);
    _scrollController.addListener(() {
      final newOpacity = (1.0 - (_scrollController.offset / 80)).clamp(
        0.0,
        1.0,
      );
      if (newOpacity != _appBarOpacity) {
        setState(() => _appBarOpacity = newOpacity);
      }
    });
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.appBackground,
      body: BlocBuilder<HomeCubit, HomeState>(
        builder: (context, state) {
          final hero = _heroItem(state);
          final forYouItems = _visibleRailItems(
            state.recommendations,
            excluded: {if (hero != null) _contentKey(hero)},
          );
          final trendingItems = _visibleRailItems(
            state.trending,
            excluded: {
              if (hero != null) _contentKey(hero),
              ...forYouItems.map(_contentKey),
            },
          );
          _precacheVisibleImages(context, [
            ?hero,
            ...forYouItems.take(8),
            ...trendingItems.take(8),
          ]);

          return Stack(
            children: [
              RefreshIndicator(
                backgroundColor: AppTheme.surface,
                color: _text,
                onRefresh: () => context.read<HomeCubit>().loadContent(),
                child: CustomScrollView(
                  controller: _scrollController,
                  physics: const BouncingScrollPhysics(
                    parent: AlwaysScrollableScrollPhysics(),
                  ),
                  slivers: [
                    SliverToBoxAdapter(
                      child: SizedBox(
                        height: MediaQuery.paddingOf(context).top + 76,
                      ),
                    ),
                    SliverToBoxAdapter(
                      child: _buildCategoryTabs(context, state),
                    ),
                    if (state.isLoading &&
                        state.recommendations.isEmpty &&
                        state.trending.isEmpty)
                      const OmniHomeSkeletonSliver()
                    else if ((state.error ?? '').isNotEmpty &&
                        state.recommendations.isEmpty &&
                        state.trending.isEmpty)
                      SliverFillRemaining(
                        hasScrollBody: false,
                        child: OmniErrorState(
                          message: state.error ?? 'Failed to load content',
                          onRetry: () =>
                              context.read<HomeCubit>().loadContent(),
                        ),
                      )
                    else
                      SliverList(
                        delegate: SliverChildListDelegate([
                          const SizedBox(height: 22),
                          _HeroRecommendation(
                            item: hero,
                            category: state.category,
                          ),
                          const SizedBox(height: 20),
                          _ReleaseCalendarCard(
                            onTap: () =>
                                _push(context, const ReleaseCalendarScreen()),
                          ),
                          const SizedBox(height: 26),
                          _ContentRail(
                            title: _forYouTitle(state.category),
                            items: forYouItems,
                            showType: state.category == ContentCategory.all,
                            onSeeAll: () =>
                                _push(context, const ForYouHubScreen()),
                          ),
                          _ContentRail(
                            title: 'Trending now',
                            items: trendingItems,
                            showType: state.category == ContentCategory.all,
                            onSeeAll: () =>
                                _push(context, const TrendingHubScreen()),
                          ),
                          _CollectionsRail(
                            onSeeAll: () =>
                                _push(context, const CollectionsScreen()),
                          ),
                          ..._extraSections(state),
                          const SizedBox(height: 104),
                        ]),
                      ),
                  ],
                ),
              ),
              Positioned(
                top: 0,
                left: 0,
                right: 0,
                child: Opacity(
                  opacity: _appBarOpacity,
                  child: _buildHeader(context),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  void _precacheVisibleImages(
    BuildContext context,
    List<UnifiedContent> items,
  ) {
    final urls = items
        .map((item) => item.imageUrl?.trim() ?? '')
        .where((url) => url.isNotEmpty)
        .take(18)
        .toList(growable: false);
    final signature = urls.join('|');
    if (signature.isEmpty || signature == _lastPrecacheSignature) return;
    _lastPrecacheSignature = signature;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      for (final url in urls) {
        precacheImage(CachedNetworkImageProvider(url), context);
      }
    });
  }

  Widget _buildHeader(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            AppTheme.appBackground.withValues(alpha: 0.96),
            Colors.transparent,
          ],
        ),
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 10),
          child: BlocBuilder<AuthCubit, AuthState>(
            builder: (context, authState) {
              final username = authState is AuthAuthenticated
                  ? authState.user.username
                  : 'User';

              return Row(
                children: [
                  const Expanded(
                    child: Text(
                      'Home',
                      textAlign: TextAlign.left,
                      style: TextStyle(
                        color: _text,
                        fontSize: 24,
                        fontWeight: FontWeight.w600,
                        height: 1.12,
                      ),
                    ),
                  ),
                  UserAvatar(
                    username: username,
                    size: 42,
                    onTap: () {
                      final userRepository = context.read<UserRepository>();
                      _push(
                        context,
                        ProfileScreen(userRepository: userRepository),
                      );
                    },
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildCategoryTabs(BuildContext context, HomeState state) {
    const tabs = [
      (ContentCategory.movie, 'Movies'),
      (ContentCategory.music, 'Music'),
      (ContentCategory.book, 'Books'),
    ];

    return Padding(
      padding: const EdgeInsets.fromLTRB(
        _tabHorizontalPadding,
        22,
        _tabHorizontalPadding,
        0,
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: tabs.map((tab) {
          final selected = state.category == tab.$1;
          return GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: () => context.read<HomeCubit>().setCategory(tab.$1),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    tab.$2,
                    style: TextStyle(
                      color: _text.withValues(alpha: selected ? 1 : 0.6),
                      fontSize: 16,
                      fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                      height: 1,
                    ),
                  ),
                  const SizedBox(height: 8),
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 180),
                    width: selected ? 18 : 0,
                    height: 2,
                    decoration: BoxDecoration(
                      color: _accent,
                      borderRadius: BorderRadius.circular(999),
                    ),
                  ),
                ],
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  List<Widget> _extraSections(HomeState state) {
    return state.homeMap.entries
        .where((entry) {
          if (entry.value.isEmpty) return false;
          final key = entry.key.toLowerCase();
          return key != 'for you' && key != 'trending now' && key != 'trending';
        })
        .take(2)
        .map(
          (entry) => _ContentRail(
            title: entry.key,
            items: entry.value,
            showType: state.category == ContentCategory.all,
          ),
        )
        .toList();
  }

  UnifiedContent? _heroItem(HomeState state) {
    if (state.recommendations.isNotEmpty) return state.recommendations.first;
    if (state.trending.isNotEmpty) return state.trending.first;
    for (final list in state.homeMap.values) {
      if (list.isNotEmpty) return list.first;
    }
    return null;
  }

  static List<UnifiedContent> _visibleRailItems(
    List<UnifiedContent> items, {
    required Set<String> excluded,
  }) {
    final seen = <String>{...excluded};
    final result = <UnifiedContent>[];

    for (final item in items) {
      final key = _contentKey(item);
      if (key.isEmpty || seen.contains(key)) continue;
      seen.add(key);
      result.add(item);
    }

    return result;
  }

  static String _contentKey(UnifiedContent item) {
    final externalId = item.externalId.trim();
    if (externalId.isNotEmpty) return '${item.type}:$externalId';
    return '${item.type}:${item.id}';
  }

  static String _forYouTitle(ContentCategory category) {
    switch (category) {
      case ContentCategory.all:
        return 'For you';
      case ContentCategory.movie:
        return 'Movies for you';
      case ContentCategory.music:
        return 'Music for you';
      case ContentCategory.book:
        return 'Books for you';
    }
  }

  static void _push(BuildContext context, Widget page) {
    Navigator.push(context, CupertinoPageRoute(builder: (_) => page));
  }
}

class _ReleaseCalendarCard extends StatelessWidget {
  final VoidCallback onTap;

  const _ReleaseCalendarCard({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: _HomeScreenState._horizontalPadding,
      ),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AppTheme.surface.withValues(alpha: 0.82),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: AppTheme.ink.withValues(alpha: 0.08)),
          ),
          child: Row(
            children: [
              Container(
                width: 44,
                height: 44,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: AppTheme.ink.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  PhosphorIcons.calendarDots(PhosphorIconsStyle.regular),
                  color: AppTheme.primary,
                  size: 23,
                ),
              ),
              const SizedBox(width: 13),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Release Calendar',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: AppTheme.ink,
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Recent and upcoming drops',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: AppTheme.ink.withValues(alpha: 0.56),
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                CupertinoIcons.chevron_right,
                color: AppTheme.ink.withValues(alpha: 0.38),
                size: 18,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _HeroRecommendation extends StatelessWidget {
  final UnifiedContent? item;
  final ContentCategory category;

  const _HeroRecommendation({required this.item, required this.category});

  @override
  Widget build(BuildContext context) {
    final content = item;
    final imageUrl = (content?.imageUrl ?? '').trim();

    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: _HomeScreenState._horizontalPadding,
      ),
      child: GestureDetector(
        onLongPress: content == null
            ? null
            : () => ContentQuickActions.show(
                context,
                content,
                source: 'home_hero',
              ),
        onTap: content == null
            ? null
            : () {
                _trackOpen(context, content, 'home_hero');
                Navigator.push(
                  context,
                  CupertinoPageRoute(
                    builder: (_) => DetailScreen(content: content),
                  ),
                );
              },
        child: ClipRRect(
          borderRadius: BorderRadius.circular(24),
          child: SizedBox(
            height: 214,
            width: double.infinity,
            child: Stack(
              fit: StackFit.expand,
              children: [
                _heroGradient(),
                if (imageUrl.isNotEmpty)
                  Positioned(
                    left: 4,
                    top: 4,
                    right: 4,
                    bottom: 4,
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(20),
                      child: OmniCachedImage(
                        imageUrl: imageUrl,
                        fallback: const SizedBox.shrink(),
                      ),
                    ),
                  ),
                Positioned.fill(
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: [
                          Colors.black.withValues(alpha: 0.08),
                          Colors.black.withValues(alpha: 0.18),
                          Colors.black.withValues(alpha: 0.66),
                        ],
                      ),
                    ),
                  ),
                ),
                Positioned(
                  left: 22,
                  right: 22,
                  bottom: 22,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        _heroReason(content) ?? _heroEyebrow(category),
                        style: TextStyle(
                          color: AppTheme.ink.withValues(alpha: 0.76),
                          fontSize: 13,
                          fontWeight: FontWeight.w400,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        content?.title ?? 'Your next pick is loading',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: AppTheme.ink,
                          fontSize: 24,
                          fontWeight: FontWeight.w600,
                          height: 1.08,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _heroSubtitle(content),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: AppTheme.ink.withValues(alpha: 0.76),
                          fontSize: 13,
                          fontWeight: FontWeight.w400,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  static Widget _heroGradient() {
    return const DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF07111F), Color(0xFF0A84FF), Color(0xFF00C2FF)],
        ),
      ),
    );
  }

  static String _heroEyebrow(ContentCategory category) {
    switch (category) {
      case ContentCategory.all:
        return "Today's pick";
      case ContentCategory.movie:
        return 'Movie pick';
      case ContentCategory.music:
        return 'Music pick';
      case ContentCategory.book:
        return 'Book pick';
    }
  }

  static String _heroSubtitle(UnifiedContent? item) {
    if (item == null) return 'Personalized recommendations will appear here';
    final parts = <String>[_typeLabel(item.type)];
    if (item.rating > 0) parts.add(item.rating.toStringAsFixed(1));
    if (item.genres.isNotEmpty) parts.add(item.genres.take(2).join(', '));
    return parts.join('  ');
  }

  static String? _heroReason(UnifiedContent? item) {
    final reason = item?.recommendationReason?.trim();
    if (reason == null || reason.isEmpty) return null;
    return reason;
  }
}

class _ContentRail extends StatelessWidget {
  final String title;
  final List<UnifiedContent> items;
  final bool showType;
  final VoidCallback? onSeeAll;

  const _ContentRail({
    required this.title,
    required this.items,
    this.showType = false,
    this.onSeeAll,
  });

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();
    final clusters = groupMusicAlbums(items).take(12).toList();
    if (clusters.isEmpty) return const SizedBox.shrink();
    final railHeight =
        clusters.any((cluster) => cluster.primary.type != 'music')
        ? 232.0
        : 188.0;

    return Padding(
      padding: const EdgeInsets.only(bottom: 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionHeader(title: title, onSeeAll: onSeeAll),
          const SizedBox(height: 14),
          SizedBox(
            height: railHeight,
            child: ListView.separated(
              physics: const BouncingScrollPhysics(),
              padding: const EdgeInsets.symmetric(
                horizontal: _HomeScreenState._horizontalPadding,
              ),
              scrollDirection: Axis.horizontal,
              itemCount: clusters.length,
              separatorBuilder: (context, index) => const SizedBox(width: 14),
              itemBuilder: (context, index) {
                return _HomeContentTile(
                  cluster: clusters[index],
                  showType: showType,
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _HomeContentTile extends StatelessWidget {
  final ContentCluster cluster;
  final bool showType;

  const _HomeContentTile({required this.cluster, required this.showType});

  @override
  Widget build(BuildContext context) {
    final item = cluster.primary;
    final width = item.type == 'music' ? 128.0 : 122.0;

    return SizedBox(
      width: width,
      child: GestureDetector(
        onLongPress: () =>
            ContentQuickActions.show(context, item, source: 'home'),
        onTap: () {
          _trackOpen(context, item, 'home_rail');
          Navigator.push(
            context,
            CupertinoPageRoute(
              builder: (_) =>
                  DetailScreen(content: item, groupedItems: cluster.items),
            ),
          );
        },
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            AspectRatio(
              aspectRatio: ContentArtwork.aspectRatioFor(item.type),
              child: Stack(
                fit: StackFit.expand,
                children: [
                  ContentArtwork(
                    item: item,
                    borderRadius: 18,
                    grouped: cluster.isMusicAlbumGroup,
                    memCacheWidth: 420,
                  ),
                  Positioned(
                    top: 8,
                    right: 8,
                    child: _FavoriteButton(item: item, size: 32),
                  ),
                  if (cluster.isMusicAlbumGroup)
                    Positioned(
                      right: 8,
                      bottom: 8,
                      child: _TrackCountBadge(count: cluster.trackCount),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 8),
            Text(
              cluster.displayTitle,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppTheme.ink,
                fontSize: 13,
                fontWeight: FontWeight.w500,
                height: 1.1,
              ),
            ),
            const SizedBox(height: 3),
            Text(
              cluster.displaySubtitle(showType: showType),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: AppTheme.ink.withValues(alpha: 0.58),
                fontSize: 11,
                fontWeight: FontWeight.w400,
                height: 1,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FavoriteButton extends StatelessWidget {
  final UnifiedContent item;
  final double size;

  const _FavoriteButton({required this.item, required this.size});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<LibraryCubit, LibraryState>(
      builder: (context, state) {
        final isLiked = state is LibraryLoaded
            ? state.favorites.any((fav) => fav.externalId == item.externalId)
            : false;

        return GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: () => context.read<LibraryCubit>().toggleFavorite(item),
          child: ClipOval(
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
              child: Container(
                width: size,
                height: size,
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.28),
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: AppTheme.ink.withValues(alpha: 0.12),
                  ),
                ),
                child: Icon(
                  PhosphorIcons.heart(
                    isLiked
                        ? PhosphorIconsStyle.fill
                        : PhosphorIconsStyle.regular,
                  ),
                  color: isLiked ? const Color(0xFFFF5D73) : AppTheme.ink,
                  size: size * 0.48,
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

class _TrackCountBadge extends StatelessWidget {
  final int count;

  const _TrackCountBadge({required this.count});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.62),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppTheme.ink.withValues(alpha: 0.08)),
      ),
      child: Text(
        '$count tracks',
        style: const TextStyle(
          color: AppTheme.ink,
          fontSize: 10,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _CollectionsRail extends StatelessWidget {
  final VoidCallback onSeeAll;

  const _CollectionsRail({required this.onSeeAll});

  @override
  Widget build(BuildContext context) {
    const collections = [
      _CollectionPreview(
        title: 'Cyber Mood',
        subtitle: 'Cyberpunk, noir',
        icon: CupertinoIcons.moon_stars_fill,
      ),
      _CollectionPreview(
        title: 'Late Night',
        subtitle: 'Chill, dark',
        icon: CupertinoIcons.music_note_2,
      ),
      _CollectionPreview(
        title: 'Mind Benders',
        subtitle: 'Mystery, surreal',
        icon: CupertinoIcons.sparkles,
      ),
      _CollectionPreview(
        title: 'Epic Worlds',
        subtitle: 'Fantasy, epic',
        icon: CupertinoIcons.book_fill,
      ),
    ];

    return Padding(
      padding: const EdgeInsets.only(bottom: 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionHeader(title: 'Collections', onSeeAll: onSeeAll),
          const SizedBox(height: 14),
          SizedBox(
            height: 144,
            child: ListView.separated(
              physics: const BouncingScrollPhysics(),
              padding: const EdgeInsets.symmetric(
                horizontal: _HomeScreenState._horizontalPadding,
              ),
              scrollDirection: Axis.horizontal,
              itemBuilder: (context, index) {
                final item = collections[index];
                return _CollectionCard(
                  item: item,
                  onTap: () => Navigator.push(
                    context,
                    CupertinoPageRoute(
                      builder: (_) =>
                          CollectionsScreen(initialCollectionTitle: item.title),
                    ),
                  ),
                );
              },
              separatorBuilder: (context, index) => const SizedBox(width: 14),
              itemCount: collections.length,
            ),
          ),
        ],
      ),
    );
  }
}

class _CollectionCard extends StatelessWidget {
  final _CollectionPreview item;
  final VoidCallback onTap;

  const _CollectionCard({required this.item, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 226,
        padding: const EdgeInsets.fromLTRB(16, 15, 16, 15),
        decoration: BoxDecoration(
          color: AppTheme.surfaceAlt,
          borderRadius: BorderRadius.circular(18),
        ),
        child: Row(
          children: [
            Container(
              width: 42,
              height: 42,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(13),
                border: Border.all(color: AppTheme.ink.withValues(alpha: 0.06)),
              ),
              child: Icon(item.icon, color: AppTheme.primary, size: 23),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppTheme.ink,
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(
                    item.subtitle,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: AppTheme.ink.withValues(alpha: 0.54),
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  final VoidCallback? onSeeAll;

  const _SectionHeader({required this.title, this.onSeeAll});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: _HomeScreenState._horizontalPadding,
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppTheme.ink,
                fontSize: 14,
                fontWeight: FontWeight.w400,
              ),
            ),
          ),
          if (onSeeAll != null)
            GestureDetector(
              onTap: onSeeAll,
              child: const Text(
                'See all',
                style: TextStyle(
                  color: _HomeScreenState._accent,
                  fontSize: 14,
                  fontWeight: FontWeight.w400,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _CollectionPreview {
  final String title;
  final String subtitle;
  final IconData icon;

  const _CollectionPreview({
    required this.title,
    required this.subtitle,
    required this.icon,
  });
}

void _trackOpen(BuildContext context, UnifiedContent item, String source) {
  context.read<AnalyticsRepository>().trackEvent(
    type: 'view',
    extId: item.externalId,
    contentType: item.type,
    meta: {
      'source': source,
      'title': item.title,
      'image_url': item.imageUrl,
      'rating': item.rating,
      'release_date': item.releaseDate,
      'genres': item.genres,
    },
  );
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
