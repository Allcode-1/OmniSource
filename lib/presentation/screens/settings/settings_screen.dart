import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/theme/app_theme.dart';
import '../../../domain/repositories/analytics_repository.dart';
import '../../widgets/app_screen_chrome.dart';
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
            subtitle: 'Personalization, activity and app controls',
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 110),
            sliver: SliverList(
              delegate: SliverChildListDelegate([
                OmniCard(
                  padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
                  child: Row(
                    children: [
                      Container(
                        width: 38,
                        height: 38,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: AppTheme.primary.withValues(alpha: 0.14),
                          borderRadius: BorderRadius.circular(11),
                        ),
                        child: const Icon(
                          CupertinoIcons.slider_horizontal_3,
                          color: AppTheme.primary,
                          size: 20,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
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
                              'Hybrid ML mixes behavior and content signals',
                              style: TextStyle(
                                color: AppTheme.ink.withValues(alpha: 0.52),
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
                        iconColor: AppTheme.primary,
                        title: 'Notifications',
                        subtitle: 'Digest and recommendation tips',
                        onTap: () => _push(const NotificationsScreen()),
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
                        iconColor: AppTheme.primary,
                        title: 'Stats',
                        subtitle: 'CTR, saves and dwell time',
                        onTap: () => _push(const StatsScreen()),
                      ),
                      _Divider(),
                      OmniRowTile(
                        icon: CupertinoIcons.time_solid,
                        iconColor: AppTheme.primary,
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
                        iconColor: AppTheme.primary,
                        title: 'Debug Panel',
                        subtitle: 'A/B mode and backend health',
                        onTap: () => _push(const DebugPanelScreen()),
                      ),
                      _Divider(),
                      OmniRowTile(
                        icon: CupertinoIcons.cloud_download_fill,
                        iconColor: AppTheme.primary,
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
        letterSpacing: 0,
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
