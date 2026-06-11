import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';

class MinimalPageHeader extends StatelessWidget {
  final String title;

  const MinimalPageHeader({super.key, required this.title});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 6, 20, 8),
        child: SizedBox(
          height: 40,
          child: Stack(
            alignment: Alignment.center,
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: IconButton(
                  onPressed: () => Navigator.maybePop(context),
                  icon: const Icon(CupertinoIcons.back, size: 24),
                  color: AppTheme.ink,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(
                    minWidth: 44,
                    minHeight: 44,
                  ),
                ),
              ),
              Text(
                title,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: AppTheme.ink,
                  fontSize: 24,
                  fontWeight: FontWeight.w600,
                  height: 1.12,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class MinimalTypeTabs extends StatelessWidget {
  final String activeType;
  final ValueChanged<String> onChanged;
  final bool includeAll;

  const MinimalTypeTabs({
    super.key,
    required this.activeType,
    required this.onChanged,
    this.includeAll = true,
  });

  @override
  Widget build(BuildContext context) {
    final tabs = [
      if (includeAll) ('All', 'all'),
      ('Movies', 'movie'),
      ('Music', 'music'),
      ('Books', 'book'),
    ];

    return Padding(
      padding: const EdgeInsets.fromLTRB(40, 22, 40, 0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: tabs.map((tab) {
          final selected = activeType == tab.$2;
          return GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: () => onChanged(tab.$2),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    tab.$1,
                    style: TextStyle(
                      color: AppTheme.ink.withValues(alpha: selected ? 1 : 0.6),
                      fontSize: 16,
                      fontWeight: FontWeight.w400,
                      height: 1,
                    ),
                  ),
                  const SizedBox(height: 8),
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 180),
                    width: selected ? 18 : 0,
                    height: 2,
                    decoration: BoxDecoration(
                      color: AppTheme.ink,
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
}

class SubtleCountText extends StatelessWidget {
  final String text;

  const SubtleCountText({super.key, required this.text});

  @override
  Widget build(BuildContext context) {
    if (text.trim().isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 18, 24, 0),
      child: Text(
        text,
        style: TextStyle(
          color: AppTheme.ink.withValues(alpha: 0.58),
          fontSize: 13,
          fontWeight: FontWeight.w400,
          height: 1.35,
        ),
      ),
    );
  }
}
