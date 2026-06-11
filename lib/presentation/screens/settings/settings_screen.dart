import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../core/theme/app_theme.dart';
import '../../../domain/repositories/analytics_repository.dart';
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
      body: SafeArea(
        child: SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(20, 10, 20, 34),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const _SettingsTopBar(),
              const SizedBox(height: 26),
              Text(
                'Personalization, activity and app controls',
                style: TextStyle(
                  color: AppTheme.ink.withValues(alpha: 0.58),
                  fontSize: 15,
                  height: 1.35,
                ),
              ),
              const SizedBox(height: 24),
              _SettingsGroup(
                children: [
                  _SettingsRow(
                    icon: CupertinoIcons.slider_horizontal_3,
                    title: 'Ranking Mode',
                    subtitle: 'Hybrid ML mixes behavior and content signals',
                    trailing: CupertinoSwitch(
                      value: isHybrid,
                      onChanged: _toggleVariant,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 26),
              const _SectionLabel('APP'),
              const SizedBox(height: 9),
              _SettingsGroup(
                children: [
                  _SettingsRow(
                    icon: CupertinoIcons.bell_fill,
                    title: 'Notifications',
                    subtitle: 'Digest and recommendation tips',
                    onTap: () => _push(const NotificationsScreen()),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              const _SectionLabel('ACTIVITY'),
              const SizedBox(height: 9),
              _SettingsGroup(
                children: [
                  _SettingsRow(
                    icon: CupertinoIcons.chart_bar_alt_fill,
                    title: 'Stats',
                    subtitle: 'CTR, saves and dwell time',
                    onTap: () => _push(const StatsScreen()),
                  ),
                  const _SettingsDivider(),
                  _SettingsRow(
                    icon: CupertinoIcons.time_solid,
                    title: 'Activity Timeline',
                    subtitle: 'Views, opens, likes and searches',
                    onTap: () => _push(const ActivityTimelineScreen()),
                  ),
                ],
              ),
              const SizedBox(height: 24),
              const _SectionLabel('SYSTEM'),
              const SizedBox(height: 9),
              _SettingsGroup(
                children: [
                  _SettingsRow(
                    icon: CupertinoIcons.wrench_fill,
                    title: 'Debug Panel',
                    subtitle: 'A/B mode and backend health',
                    onTap: () => _push(const DebugPanelScreen()),
                  ),
                  const _SettingsDivider(),
                  _SettingsRow(
                    icon: CupertinoIcons.cloud_download_fill,
                    title: 'Offline Queue',
                    subtitle: 'Pending analytics events',
                    onTap: () => _push(const OfflineQueueScreen()),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SettingsTopBar extends StatelessWidget {
  const _SettingsTopBar();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: 46,
          height: 46,
          child: IconButton(
            onPressed: () => Navigator.maybePop(context),
            icon: const Icon(CupertinoIcons.back, size: 28),
            color: AppTheme.ink,
            padding: EdgeInsets.zero,
            style: IconButton.styleFrom(
              backgroundColor: AppTheme.surfaceAlt,
              shape: const CircleBorder(),
            ),
          ),
        ),
        const SizedBox(width: 10),
        const Expanded(
          child: Text(
            'Settings',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: AppTheme.ink,
              fontSize: 32,
              fontWeight: FontWeight.w700,
              height: 1.04,
            ),
          ),
        ),
      ],
    );
  }
}

class _SettingsGroup extends StatelessWidget {
  final List<Widget> children;

  const _SettingsGroup({required this.children});

  @override
  Widget build(BuildContext context) {
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: AppTheme.surfaceAlt,
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(children: children),
    );
  }
}

class _SettingsRow extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;
  final Widget? trailing;

  const _SettingsRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.onTap,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
        child: Row(
          children: [
            Icon(icon, color: AppTheme.primary, size: 23),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppTheme.ink,
                      fontSize: 17,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    subtitle,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: AppTheme.ink.withValues(alpha: 0.52),
                      fontSize: 13,
                      height: 1.25,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            trailing ??
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

class _SectionLabel extends StatelessWidget {
  final String text;

  const _SectionLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: TextStyle(
        color: AppTheme.ink.withValues(alpha: 0.48),
        fontSize: 12,
        fontWeight: FontWeight.w700,
        letterSpacing: 0,
      ),
    );
  }
}

class _SettingsDivider extends StatelessWidget {
  const _SettingsDivider();

  @override
  Widget build(BuildContext context) {
    return Divider(
      height: 1,
      indent: 55,
      color: AppTheme.ink.withValues(alpha: 0.1),
    );
  }
}
