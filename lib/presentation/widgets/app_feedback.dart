import 'package:flutter/cupertino.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:shimmer/shimmer.dart';

import '../../core/theme/app_theme.dart';

class OmniLoadingState extends StatelessWidget {
  final String message;

  const OmniLoadingState({super.key, this.message = 'Loading'});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CupertinoActivityIndicator(color: AppTheme.primary),
          const SizedBox(height: 14),
          Text(
            message,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: AppTheme.ink.withValues(alpha: 0.52),
              fontSize: 14,
            ),
          ),
        ],
      ),
    );
  }
}

class OmniEmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;

  const OmniEmptyState({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
    this.actionLabel,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(26),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: AppTheme.ink.withValues(alpha: 0.34), size: 36),
            const SizedBox(height: 14),
            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: AppTheme.ink,
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            if (subtitle != null && subtitle!.trim().isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                subtitle!,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: AppTheme.ink.withValues(alpha: 0.52),
                  fontSize: 13,
                  height: 1.35,
                ),
              ),
            ],
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: 16),
              GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: onAction,
                child: Text(
                  actionLabel!,
                  style: const TextStyle(
                    color: AppTheme.primary,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class OmniErrorState extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;

  const OmniErrorState({super.key, required this.message, this.onRetry});

  @override
  Widget build(BuildContext context) {
    return OmniEmptyState(
      icon: PhosphorIcons.warningCircle(PhosphorIconsStyle.light),
      title: 'Something went wrong',
      subtitle: message,
      actionLabel: onRetry == null ? null : 'Retry',
      onAction: onRetry,
    );
  }
}

class OmniGridSkeletonSliver extends StatelessWidget {
  final int itemCount;
  final EdgeInsetsGeometry padding;

  const OmniGridSkeletonSliver({
    super.key,
    this.itemCount = 6,
    this.padding = const EdgeInsets.fromLTRB(20, 0, 20, 104),
  });

  @override
  Widget build(BuildContext context) {
    return SliverPadding(
      padding: padding,
      sliver: SliverGrid(
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          crossAxisSpacing: 16,
          mainAxisSpacing: 18,
          childAspectRatio: 0.63,
        ),
        delegate: SliverChildBuilderDelegate(
          (context, index) => const _SkeletonTile(),
          childCount: itemCount,
        ),
      ),
    );
  }
}

class OmniHomeSkeletonSliver extends StatelessWidget {
  const OmniHomeSkeletonSliver({super.key});

  @override
  Widget build(BuildContext context) {
    return SliverList(
      delegate: SliverChildListDelegate([
        const SizedBox(height: 22),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 20),
          child: _SkeletonBlock(height: 214, radius: 28),
        ),
        const SizedBox(height: 28),
        _SkeletonRail(titleWidth: 72),
        const SizedBox(height: 26),
        _SkeletonRail(titleWidth: 104),
        const SizedBox(height: 110),
      ]),
    );
  }
}

class _SkeletonRail extends StatelessWidget {
  final double titleWidth;

  const _SkeletonRail({required this.titleWidth});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: _SkeletonBlock(width: titleWidth, height: 15, radius: 8),
        ),
        const SizedBox(height: 14),
        SizedBox(
          height: 186,
          child: ListView.separated(
            physics: const NeverScrollableScrollPhysics(),
            padding: const EdgeInsets.symmetric(horizontal: 20),
            scrollDirection: Axis.horizontal,
            itemCount: 4,
            separatorBuilder: (context, index) => const SizedBox(width: 14),
            itemBuilder: (context, index) =>
                const SizedBox(width: 118, child: _SkeletonTile()),
          ),
        ),
      ],
    );
  }
}

class _SkeletonTile extends StatelessWidget {
  const _SkeletonTile();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: const [
        Expanded(child: _SkeletonBlock(radius: 20)),
        SizedBox(height: 9),
        _SkeletonBlock(width: 92, height: 12, radius: 8),
        SizedBox(height: 7),
        _SkeletonBlock(width: 58, height: 10, radius: 8),
      ],
    );
  }
}

class _SkeletonBlock extends StatelessWidget {
  final double? width;
  final double? height;
  final double radius;

  const _SkeletonBlock({this.width, this.height, this.radius = 14});

  @override
  Widget build(BuildContext context) {
    return Shimmer.fromColors(
      baseColor: AppTheme.surface.withValues(alpha: 0.72),
      highlightColor: AppTheme.surfaceAlt.withValues(alpha: 0.88),
      child: Container(
        width: width,
        height: height,
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(radius),
        ),
      ),
    );
  }
}
