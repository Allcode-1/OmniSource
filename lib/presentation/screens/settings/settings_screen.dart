import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../core/theme/app_theme.dart';
import '../../../domain/repositories/analytics_repository.dart';
import '../../widgets/app_screen_chrome.dart';
import '../calendar/release_calendar_screen.dart';
import '../notifications/notifications_screen.dart';
import '../stats/stats_screen.dart';
import '../timeline/activity_timeline_screen.dart';
import 'debug_panel_screen.dart';
import 'offline_queue_screen.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  String _variant = 'hybrid_ml';

  @override
  void initState() {
    super.initState();
    _loadVariant();
  }

  Future<void> _loadVariant() async {
    final variant = await context
        .read<AnalyticsRepository>()
        .getRankingVariant();
    if (!mounted) return;
    setState(() => _variant = variant);
  }

  Future<void> _toggleVariant(bool isHybrid) async {
    final next = isHybrid ? 'hybrid_ml' : 'content_only';
    final updated = await context.read<AnalyticsRepository>().setRankingVariant(
      next,
    );
    if (!mounted) return;
    setState(() => _variant = updated);
  }

  void _push(Widget page) {
    Navigator.push(context, CupertinoPageRoute(builder: (_) => page));
  }

  @override
  Widget build(BuildContext context) {
    final isHybrid = _variant == 'hybrid_ml';
    return Scaffold(
      backgroundColor: AppTheme.appBackground,
      body: CustomScrollView(
        physics: const BouncingScrollPhysics(),
        slivers: [
          const OmniHeaderSliver(
            title: 'Settings',
            subtitle: 'Recommendations, activity and app diagnostics',
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 110),
            sliver: SliverList(
              delegate: SliverChildListDelegate([
                OmniCard(
                  padding: const EdgeInsets.fromLTRB(16, 14, 14, 14),
                  child: Row(
                    children: [
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Ranking Mode',
                              style: TextStyle(
                                fontWeight: FontWeight.w600,
                                fontSize: 16,
                              ),
                            ),
                            SizedBox(height: 5),
                            Text(
                              'Hybrid ML mixes behavior with content signals',
                              style: TextStyle(
                                color: Colors.white54,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ),
                      CupertinoSwitch(
                        value: isHybrid,
                        onChanged: _toggleVariant,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 22),
                _SectionLabel('APP'),
                const SizedBox(height: 8),
                OmniCard(
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                  child: Column(
                    children: [
                      OmniRowTile(
                        icon: CupertinoIcons.bell_fill,
                        title: 'Notifications',
                        subtitle: 'Digest and recommendation tips',
                        onTap: () => _push(const NotificationsScreen()),
                      ),
                      _Divider(),
                      OmniRowTile(
                        icon: PhosphorIcons.calendarDots(
                          PhosphorIconsStyle.regular,
                        ),
                        title: 'Release Calendar',
                        subtitle: 'Recent and upcoming drops',
                        onTap: () => _push(const ReleaseCalendarScreen()),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 22),
                _SectionLabel('ACTIVITY'),
                const SizedBox(height: 8),
                OmniCard(
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                  child: Column(
                    children: [
                      OmniRowTile(
                        icon: CupertinoIcons.chart_bar_alt_fill,
                        title: 'Stats',
                        subtitle: 'CTR, saves and dwell time',
                        onTap: () => _push(const StatsScreen()),
                      ),
                      _Divider(),
                      OmniRowTile(
                        icon: CupertinoIcons.time_solid,
                        title: 'Activity Timeline',
                        subtitle: 'Views, opens, likes and searches',
                        onTap: () => _push(const ActivityTimelineScreen()),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 22),
                _SectionLabel('SYSTEM'),
                const SizedBox(height: 8),
                OmniCard(
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                  child: Column(
                    children: [
                      OmniRowTile(
                        icon: CupertinoIcons.wrench_fill,
                        title: 'Debug Panel',
                        subtitle: 'A/B mode and backend health',
                        onTap: () => _push(const DebugPanelScreen()),
                      ),
                      _Divider(),
                      OmniRowTile(
                        icon: CupertinoIcons.cloud_download_fill,
                        title: 'Offline Queue',
                        subtitle: 'Pending analytics events',
                        onTap: () => _push(const OfflineQueueScreen()),
                      ),
                    ],
                  ),
                ),
              ]),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  final String text;

  const _SectionLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: TextStyle(
        color: AppTheme.ink.withValues(alpha: 0.48),
        fontSize: 11,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.8,
      ),
    );
  }
}

class _Divider extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Divider(
      height: 1,
      indent: 40,
      color: AppTheme.ink.withValues(alpha: 0.08),
    );
  }
}
