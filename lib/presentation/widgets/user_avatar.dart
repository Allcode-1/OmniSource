import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';

class UserAvatar extends StatelessWidget {
  final String username;
  final double size;
  final VoidCallback? onTap;

  const UserAvatar({
    super.key,
    required this.username,
    this.size = 40,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final palette = _paletteFor(username);
    final letter = _letterFor(username);

    final avatar = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: palette,
        ),
        border: Border.all(color: AppTheme.ink.withValues(alpha: 0.14)),
        boxShadow: [
          BoxShadow(
            color: palette.last.withValues(alpha: 0.24),
            blurRadius: 16,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Center(
        child: Text(
          letter,
          style: TextStyle(
            color: AppTheme.ink,
            fontSize: size * 0.38,
            fontWeight: FontWeight.w600,
            height: 1,
          ),
        ),
      ),
    );

    if (onTap == null) return avatar;
    return GestureDetector(onTap: onTap, child: avatar);
  }

  static String _letterFor(String value) {
    final trimmed = value.trim();
    if (trimmed.isEmpty) return 'U';
    return trimmed.substring(0, 1).toUpperCase();
  }

  static List<Color> _paletteFor(String value) {
    const palettes = [
      [Color(0xFF0A84FF), Color(0xFF00C2FF)],
      [Color(0xFF2563EB), Color(0xFF22C55E)],
      [Color(0xFF30D158), Color(0xFF34C759)],
      [Color(0xFF38BDF8), Color(0xFF6366F1)],
      [Color(0xFFFFD60A), Color(0xFFFF453A)],
      [Color(0xFF64D2FF), Color(0xFF30D158)],
    ];

    final source = value.trim().isEmpty ? 'user' : value.trim().toLowerCase();
    final hash = source.codeUnits.fold<int>(
      0,
      (acc, unit) => (acc * 31 + unit) & 0x7fffffff,
    );
    return palettes[hash % palettes.length];
  }
}
