import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/utils/content_display.dart';
import '../../../domain/entities/unified_content.dart';
import '../../../domain/repositories/content_repository.dart';
import '../../widgets/secondary_header_sliver.dart';
import '../search/search_grid_card.dart';

class MoodPickerScreen extends StatefulWidget {
  const MoodPickerScreen({super.key});

  @override
  State<MoodPickerScreen> createState() => _MoodPickerScreenState();
}

class _MoodPickerScreenState extends State<MoodPickerScreen> {
  static final _moods = <_MoodConfig>[
    _MoodConfig(
      id: 'focus',
      title: 'Focus Mode',
      subtitle: 'Clear mind, deep concentration',
      icon: CupertinoIcons.bolt_fill,
      color: Color(0xFF5AA9FF),
      tags: ['productivity', 'sci-fi', 'ambient'],
      type: 'all',
    ),
    _MoodConfig(
      id: 'chill',
      title: 'Chill Evening',
      subtitle: 'Relaxed and warm vibes',
      icon: CupertinoIcons.moon_stars_fill,
      color: Color(0xFF5AC8FA),
      tags: ['chill', 'lofi', 'romance'],
      type: 'music',
    ),
    _MoodConfig(
      id: 'adrenaline',
      title: 'Adrenaline Rush',
      subtitle: 'Action-heavy picks',
      icon: CupertinoIcons.flame_fill,
      color: Color(0xFFFF453A),
      tags: ['action', 'thriller', 'adventure'],
      type: 'movie',
    ),
    _MoodConfig(
      id: 'curious',
      title: 'Curious Learner',
      subtitle: 'Discover and explore',
      icon: CupertinoIcons.compass_fill,
      color: Color(0xFF30D158),
      tags: ['history', 'nonfiction', 'discovery'],
      type: 'book',
    ),
    _MoodConfig(
      id: 'night',
      title: 'Night Mystery',
      subtitle: 'Dark and intriguing stories',
      icon: CupertinoIcons.cloud_moon_bolt_fill,
      color: Color(0xFFBF5AF2),
      tags: ['mystery', 'dark', 'noir'],
      type: 'all',
    ),
  ];

  String _activeMoodId = 'focus';
  bool _loading = true;
  String _error = '';
  List<UnifiedContent> _results = const [];

  _MoodConfig get _activeMood =>
      _moods.firstWhere((mood) => mood.id == _activeMoodId);

  String _contentKey(UnifiedContent item) => '${item.type}:${item.externalId}';

  @override
  void initState() {
    super.initState();
    _loadMood();
  }

  Future<void> _loadMood() async {
    setState(() {
      _loading = true;
      _error = '';
    });
    try {
      final repo = context.read<ContentRepository>();
      final mood = _activeMood;
      final responses = await Future.wait(
        mood.tags.map(
          (tag) => repo.getDeepResearch(
            tag,
            type: mood.type == 'all' ? null : mood.type,
          ),
        ),
      );
      final merged = <String, UnifiedContent>{};
      for (final list in responses) {
        for (final item in list) {
          merged[_contentKey(item)] = item;
        }
      }
      final next = merged.values.toList()
        ..sort((a, b) => b.rating.compareTo(a.rating));
      if (!mounted) return;
      setState(() => _results = next.take(40).toList());
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Failed to load mood recommendations');
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  void _selectMood(String id) {
    if (_activeMoodId == id) return;
    setState(() => _activeMoodId = id);
    _loadMood();
  }

  @override
  Widget build(BuildContext context) {
    final mood = _activeMood;
    final displayResults = groupMusicAlbums(_results);
    return Scaffold(
      body: CustomScrollView(
        physics: const BouncingScrollPhysics(),
        slivers: [
          const SecondaryHeaderSliver(
            title: 'Mood Picker',
            subtitle: 'Pick a mood and get an instant curated feed',
            infoLabel: 'Quick mood presets tuned by tags and content type',
            infoIcon: CupertinoIcons.layers_alt_fill,
          ),
          const SliverToBoxAdapter(child: SizedBox(height: 14)),
          SliverToBoxAdapter(
            child: SizedBox(
              height: 124,
              child: ListView.builder(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                scrollDirection: Axis.horizontal,
                itemCount: _moods.length,
                itemBuilder: (context, index) {
                  final item = _moods[index];
                  final selected = item.id == _activeMoodId;
                  return _MoodCard(
                    mood: item,
                    selected: selected,
                    onTap: () => _selectMood(item.id),
                  );
                },
              ),
            ),
          ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 10, 20, 0),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFF16213A),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(mood.icon, color: mood.color, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            mood.title,
                            style: const TextStyle(
                              fontWeight: FontWeight.w700,
                              fontSize: 15,
                            ),
                          ),
                        ),
                        Text(
                          mood.type.toUpperCase(),
                          style: const TextStyle(
                            fontSize: 11,
                            color: Colors.white60,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: mood.tags
                          .map(
                            (tag) => Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 10,
                                vertical: 6,
                              ),
                              decoration: BoxDecoration(
                                color: Colors.black26,
                                borderRadius: BorderRadius.circular(999),
                              ),
                              child: Text(
                                '#$tag',
                                style: const TextStyle(fontSize: 11),
                              ),
                            ),
                          )
                          .toList(),
                    ),
                  ],
                ),
              ),
            ),
          ),
          const SliverToBoxAdapter(child: SizedBox(height: 12)),
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
                  style: const TextStyle(color: Colors.redAccent),
                ),
              ),
            )
          else if (displayResults.isEmpty)
            const SliverFillRemaining(
              hasScrollBody: false,
              child: Center(
                child: Text(
                  'No results for this mood yet',
                  style: TextStyle(color: Colors.white38),
                ),
              ),
            )
          else
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              sliver: SliverGrid(
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  crossAxisSpacing: 12,
                  mainAxisSpacing: 14,
                  childAspectRatio: contentGridAspectRatio(mood.type),
                ),
                delegate: SliverChildBuilderDelegate((context, index) {
                  final cluster = displayResults[index];
                  return SearchGridCard(
                    item: cluster.primary,
                    groupedItems: cluster.items,
                  );
                }, childCount: displayResults.length),
              ),
            ),
          const SliverToBoxAdapter(child: SizedBox(height: 100)),
        ],
      ),
    );
  }
}

class _MoodCard extends StatelessWidget {
  final _MoodConfig mood;
  final bool selected;
  final VoidCallback onTap;

  const _MoodCard({
    required this.mood,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        width: 180,
        margin: const EdgeInsets.only(right: 10),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: selected
              ? mood.color.withValues(alpha: 0.28)
              : const Color(0xFF16213A),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: selected ? mood.color : Colors.white12,
            width: selected ? 1.4 : 1.0,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(mood.icon, color: selected ? Colors.white : mood.color),
            const Spacer(),
            Text(
              mood.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 4),
            Text(
              mood.subtitle,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 12, color: Colors.white70),
            ),
          ],
        ),
      ),
    );
  }
}

class _MoodConfig {
  final String id;
  final String title;
  final String subtitle;
  final IconData icon;
  final Color color;
  final List<String> tags;
  final String type;

  const _MoodConfig({
    required this.id,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.color,
    required this.tags,
    required this.type,
  });
}
