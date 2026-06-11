import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/theme/app_theme.dart';
import '../../../domain/entities/interaction_event.dart';
import '../../../domain/repositories/analytics_repository.dart';
import '../../widgets/app_screen_chrome.dart';

class ActivityTimelineScreen extends StatefulWidget {
  const ActivityTimelineScreen({super.key});

  @override
  State<ActivityTimelineScreen> createState() => _ActivityTimelineScreenState();
}

class _ActivityTimelineScreenState extends State<ActivityTimelineScreen> {
  bool _loading = true;
  String _error = '';
  List<InteractionEvent> _events = const [];

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
      final repo = context.read<AnalyticsRepository>();
      final events = await repo.getTimeline(limit: 120);
      if (!mounted) return;
      setState(() => _events = events);
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Failed to load timeline');
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  IconData _iconForType(String type) {
    switch (type) {
      case 'open_detail':
        return CupertinoIcons.doc_text_search;
      case 'dwell_time':
        return CupertinoIcons.timer;
      case 'search':
        return CupertinoIcons.search;
      case 'preview_open':
        return CupertinoIcons.play_rectangle;
      case 'preview_play':
        return CupertinoIcons.play_fill;
      case 'external_open':
        return CupertinoIcons.arrow_up_right;
      case 'like':
        return CupertinoIcons.heart_fill;
      case 'playlist_add':
        return CupertinoIcons.add_circled_solid;
      default:
        return CupertinoIcons.circle_fill;
    }
  }

  Color _colorForType(String type) {
    switch (type) {
      case 'like':
        return const Color(0xFFFF5D73);
      case 'playlist_add':
        return const Color(0xFF4ADE80);
      case 'search':
        return AppTheme.primary;
      case 'preview_open':
      case 'preview_play':
        return const Color(0xFF38BDF8);
      case 'external_open':
        return const Color(0xFFA78BFA);
      default:
        return AppTheme.ink.withValues(alpha: 0.68);
    }
  }

  String _timeLabel(DateTime value) {
    final local = value.toLocal();
    final hh = local.hour.toString().padLeft(2, '0');
    final mm = local.minute.toString().padLeft(2, '0');
    return '${local.year}-${local.month.toString().padLeft(2, '0')}-${local.day.toString().padLeft(2, '0')} $hh:$mm';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.appBackground,
      body: CustomScrollView(
        physics: const BouncingScrollPhysics(),
        slivers: [
          const OmniHeaderSliver(
            title: 'Activity',
            subtitle: 'Views, opens, dwell time, likes and searches',
          ),
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
                  style: const TextStyle(color: Color(0xFFFF5D73)),
                ),
              ),
            )
          else if (_events.isEmpty)
            SliverFillRemaining(
              hasScrollBody: false,
              child: Center(
                child: Text(
                  'No activity yet',
                  style: TextStyle(color: AppTheme.ink.withValues(alpha: 0.42)),
                ),
              ),
            )
          else
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 110),
              sliver: SliverList.separated(
                itemBuilder: (context, index) {
                  final event = _events[index];
                  final color = _colorForType(event.type);
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Row(
                      children: [
                        Container(
                          width: 42,
                          height: 42,
                          decoration: BoxDecoration(
                            color: color.withValues(alpha: 0.18),
                            shape: BoxShape.circle,
                          ),
                          child: Icon(
                            _iconForType(event.type),
                            color: color,
                            size: 18,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                event.title?.trim().isNotEmpty == true
                                    ? event.title!
                                    : event.type,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  color: AppTheme.ink,
                                  fontWeight: FontWeight.w600,
                                  fontSize: 16,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${event.type}  -  ${_timeLabel(event.createdAt)}',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  color: AppTheme.ink.withValues(alpha: 0.48),
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          event.weight.toStringAsFixed(2),
                          style: TextStyle(
                            color: AppTheme.ink.withValues(alpha: 0.48),
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  );
                },
                separatorBuilder: (context, index) => Divider(
                  height: 1,
                  indent: 54,
                  color: AppTheme.ink.withValues(alpha: 0.08),
                ),
                itemCount: _events.length,
              ),
            ),
        ],
      ),
    );
  }
}
