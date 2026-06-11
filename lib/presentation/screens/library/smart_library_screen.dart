import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/utils/app_logger.dart';
import '../../../core/utils/content_display.dart';
import '../../../domain/entities/interaction_event.dart';
import '../../../domain/entities/usage_stats.dart';
import '../../../domain/entities/unified_content.dart';
import '../../../domain/repositories/analytics_repository.dart';
import '../../bloc/library/library_cubit.dart';
import '../../bloc/library/library_state.dart';
import '../../widgets/secondary_header_sliver.dart';
import '../search/search_grid_card.dart';

class SmartLibraryScreen extends StatefulWidget {
  const SmartLibraryScreen({super.key});

  @override
  State<SmartLibraryScreen> createState() => _SmartLibraryScreenState();
}

class _SmartLibraryScreenState extends State<SmartLibraryScreen> {
  bool _loadingAnalytics = true;
  UsageStats? _stats;
  List<InteractionEvent> _timeline = const [];
  String _analyticsError = '';

  @override
  void initState() {
    super.initState();
    context.read<LibraryCubit>().loadLibraryData();
    _loadAnalytics();
  }

  Future<void> _loadAnalytics() async {
    setState(() {
      _loadingAnalytics = true;
      _analyticsError = '';
    });
    try {
      final analytics = context.read<AnalyticsRepository>();
      final responses = await Future.wait([
        analytics.getStats(days: 30),
        analytics.getTimeline(limit: 40),
      ]);
      if (!mounted) return;
      setState(() {
        _stats = responses[0] as UsageStats;
        _timeline = responses[1] as List<InteractionEvent>;
      });
    } catch (e, st) {
      AppLogger.error(
        'Library insights loading failed',
        error: e,
        stackTrace: st,
        name: 'SmartLibraryScreen',
      );
      if (!mounted) return;
      setState(() => _analyticsError = 'Insights are temporarily unavailable');
    } finally {
      if (mounted) {
        setState(() => _loadingAnalytics = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.appBackground,
      body: BlocBuilder<LibraryCubit, LibraryState>(
        builder: (context, state) {
          if (state is LibraryLoading) {
            return const Center(child: CircularProgressIndicator());
          }
          if (state is LibraryError) {
            return Center(
              child: Text(
                state.message,
                style: const TextStyle(color: Colors.redAccent),
              ),
            );
          }
          if (state is! LibraryLoaded) {
            return const SizedBox.shrink();
          }

          final favorites = state.favorites;
          final byType = _countByType(favorites);
          final byGenre = _countByGenre(favorites);
          final recentlyLiked = favorites.reversed.take(8).toList();
          final avgRating = _avgRating(favorites);
          final playlistCoverage = _playlistCoverage(state);
          final usage = _stats;
          final recentEvents = _timeline.take(6).toList();
          final maxTypeCount = byType.values.isEmpty
              ? 1
              : byType.values.reduce((a, b) => a > b ? a : b);
          final topGenres = byGenre.entries.toList()
            ..sort((a, b) => b.value.compareTo(a.value));

          return CustomScrollView(
            physics: const BouncingScrollPhysics(),
            slivers: [
              const SecondaryHeaderSliver(
                title: 'Library Insights',
                subtitle: 'Behavior, quality and usage health of your library',
                infoLabel: 'Track favorites, playlists, engagement and quality',
                infoIcon: CupertinoIcons.chart_bar_alt_fill,
              ),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 14, 20, 0),
                  child: Row(
                    children: [
                      Expanded(
                        child: _MetricBox(
                          title: 'Favorites',
                          value: '${favorites.length}',
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _MetricBox(
                          title: 'Playlists',
                          value: '${state.playlists.length}',
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 10, 20, 0),
                  child: Row(
                    children: [
                      Expanded(
                        child: _MetricBox(
                          title: 'Avg Rating',
                          value: avgRating.toStringAsFixed(1),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _MetricBox(
                          title: 'In Playlists',
                          value: '${playlistCoverage.toStringAsFixed(0)}%',
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              if (_loadingAnalytics)
                const SliverToBoxAdapter(
                  child: Padding(
                    padding: EdgeInsets.only(top: 14),
                    child: Center(child: CupertinoActivityIndicator()),
                  ),
                )
              else if (_analyticsError.isNotEmpty)
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(20, 10, 20, 0),
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFF2A1E1E),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: Colors.redAccent.withValues(alpha: 0.3),
                        ),
                      ),
                      child: Text(
                        _analyticsError,
                        style: const TextStyle(color: Colors.redAccent),
                      ),
                    ),
                  ),
                )
              else if (usage != null)
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(20, 10, 20, 0),
                    child: Row(
                      children: [
                        Expanded(
                          child: _MetricBox(
                            title: 'CTR (30d)',
                            value: '${(usage.ctr * 100).toStringAsFixed(1)}%',
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: _MetricBox(
                            title: 'Avg Dwell',
                            value:
                                '${usage.avgDwellSeconds.toStringAsFixed(1)}s',
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 10, 20, 0),
                  child: Container(
                    padding: const EdgeInsets.all(14),
                    decoration: _insightDecoration(),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Type Distribution',
                          style: TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 16,
                          ),
                        ),
                        const SizedBox(height: 10),
                        ...byType.entries.map((entry) {
                          final ratio = entry.value / maxTypeCount;
                          return Padding(
                            padding: const EdgeInsets.symmetric(vertical: 4),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Expanded(child: Text(entry.key)),
                                    Text('${entry.value}'),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                ClipRRect(
                                  borderRadius: BorderRadius.circular(999),
                                  child: LinearProgressIndicator(
                                    minHeight: 8,
                                    value: ratio,
                                    backgroundColor: AppTheme.ink.withValues(
                                      alpha: 0.08,
                                    ),
                                    color: AppTheme.primary,
                                  ),
                                ),
                              ],
                            ),
                          );
                        }),
                      ],
                    ),
                  ),
                ),
              ),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 10, 20, 0),
                  child: Container(
                    padding: const EdgeInsets.all(14),
                    decoration: _insightDecoration(),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Top Genres',
                          style: TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 16,
                          ),
                        ),
                        const SizedBox(height: 10),
                        if (topGenres.isEmpty)
                          Text(
                            'No genres yet',
                            style: TextStyle(
                              color: AppTheme.ink.withValues(alpha: 0.52),
                            ),
                          )
                        else
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: topGenres.take(8).map((entry) {
                              return Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 10,
                                  vertical: 6,
                                ),
                                decoration: BoxDecoration(
                                  color: AppTheme.ink.withValues(alpha: 0.08),
                                  borderRadius: BorderRadius.circular(999),
                                ),
                                child: Text(
                                  '${entry.key} (${entry.value})',
                                  style: const TextStyle(fontSize: 12),
                                ),
                              );
                            }).toList(),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 10, 20, 0),
                  child: Container(
                    padding: const EdgeInsets.all(14),
                    decoration: _insightDecoration(),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Recent Activity',
                          style: TextStyle(
                            fontWeight: FontWeight.w700,
                            fontSize: 16,
                          ),
                        ),
                        const SizedBox(height: 8),
                        if (recentEvents.isEmpty)
                          Text(
                            'No events tracked yet',
                            style: TextStyle(
                              color: AppTheme.ink.withValues(alpha: 0.52),
                            ),
                          )
                        else
                          ...recentEvents.map((event) {
                            return Padding(
                              padding: const EdgeInsets.symmetric(vertical: 4),
                              child: Row(
                                children: [
                                  Icon(
                                    _iconForEvent(event.type),
                                    size: 16,
                                    color: AppTheme.ink.withValues(alpha: 0.7),
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      event.title?.trim().isNotEmpty == true
                                          ? event.title!
                                          : event.type,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                  Text(
                                    _timeAgo(event.createdAt),
                                    style: TextStyle(
                                      color: AppTheme.ink.withValues(
                                        alpha: 0.5,
                                      ),
                                      fontSize: 11,
                                    ),
                                  ),
                                ],
                              ),
                            );
                          }),
                      ],
                    ),
                  ),
                ),
              ),
              const SliverToBoxAdapter(
                child: Padding(
                  padding: EdgeInsets.fromLTRB(20, 20, 20, 12),
                  child: Text(
                    'Recently Liked',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
                  ),
                ),
              ),
              Builder(
                builder: (context) {
                  final displayItems = groupMusicAlbums(recentlyLiked);
                  return SliverPadding(
                    padding: const EdgeInsets.symmetric(horizontal: 20),
                    sliver: SliverGrid(
                      gridDelegate:
                          const SliverGridDelegateWithFixedCrossAxisCount(
                            crossAxisCount: 2,
                            crossAxisSpacing: 12,
                            mainAxisSpacing: 14,
                            childAspectRatio: 0.56,
                          ),
                      delegate: SliverChildBuilderDelegate((context, index) {
                        final cluster = displayItems[index];
                        return SearchGridCard(
                          item: cluster.primary,
                          groupedItems: cluster.items,
                        );
                      }, childCount: displayItems.length),
                    ),
                  );
                },
              ),
              const SliverToBoxAdapter(child: SizedBox(height: 100)),
            ],
          );
        },
      ),
    );
  }

  Map<String, int> _countByType(List<UnifiedContent> items) {
    final map = <String, int>{};
    for (final item in items) {
      map[item.type] = (map[item.type] ?? 0) + 1;
    }
    return map;
  }

  Map<String, int> _countByGenre(List<UnifiedContent> items) {
    final map = <String, int>{};
    for (final item in items) {
      for (final genre in item.genres) {
        final key = genre.trim();
        if (key.isEmpty) continue;
        map[key] = (map[key] ?? 0) + 1;
      }
    }
    return map;
  }

  double _avgRating(List<UnifiedContent> items) {
    if (items.isEmpty) return 0.0;
    final sum = items.fold<double>(0.0, (acc, item) => acc + item.rating);
    return sum / items.length;
  }

  double _playlistCoverage(LibraryLoaded state) {
    if (state.favorites.isEmpty) return 0.0;
    final idsInPlaylists = <String>{};
    for (final list in state.playlistItemsById.values) {
      for (final item in list) {
        idsInPlaylists.add(item.externalId);
      }
    }
    final inPlaylists = state.favorites
        .where((item) => idsInPlaylists.contains(item.externalId))
        .length;
    return (inPlaylists / state.favorites.length) * 100;
  }

  String _timeAgo(DateTime dateTime) {
    final diff = DateTime.now().difference(dateTime);
    if (diff.inDays > 0) return '${diff.inDays}d';
    if (diff.inHours > 0) return '${diff.inHours}h';
    if (diff.inMinutes > 0) return '${diff.inMinutes}m';
    return 'now';
  }

  IconData _iconForEvent(String type) {
    switch (type) {
      case 'like':
        return CupertinoIcons.heart_fill;
      case 'playlist_add':
        return CupertinoIcons.music_note_list;
      case 'open_detail':
        return CupertinoIcons.rectangle_stack_fill;
      case 'search':
        return CupertinoIcons.search;
      default:
        return CupertinoIcons.time;
    }
  }

  BoxDecoration _insightDecoration() {
    return BoxDecoration(
      color: AppTheme.surface.withValues(alpha: 0.82),
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: AppTheme.ink.withValues(alpha: 0.08)),
    );
  }
}

class _MetricBox extends StatelessWidget {
  final String title;
  final String value;
  const _MetricBox({required this.title, required this.value});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surface.withValues(alpha: 0.82),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.ink.withValues(alpha: 0.08)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(color: AppTheme.ink.withValues(alpha: 0.52)),
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}
