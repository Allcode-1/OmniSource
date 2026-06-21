import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../domain/entities/unified_content.dart';
import 'omni_cached_image.dart';

class ContentArtwork extends StatelessWidget {
  final UnifiedContent item;
  final double borderRadius;
  final int? memCacheWidth;
  final bool grouped;

  const ContentArtwork({
    super.key,
    required this.item,
    this.borderRadius = 16,
    this.memCacheWidth,
    this.grouped = false,
  });

  static double aspectRatioFor(String type) {
    switch (type) {
      case 'movie':
        return 2 / 3;
      case 'book':
        return 0.68;
      default:
        return 1;
    }
  }

  @override
  Widget build(BuildContext context) {
    final imageUrl = (item.imageUrl ?? '').trim();
    final isBook = item.type == 'book';

    return ClipRRect(
      borderRadius: BorderRadius.circular(borderRadius),
      child: Stack(
        fit: StackFit.expand,
        children: [
          DecoratedBox(
            decoration: BoxDecoration(
              color: isBook ? const Color(0xFF111113) : AppTheme.surfaceAlt,
            ),
          ),
          Padding(
            padding: EdgeInsets.all(isBook ? 8 : 0),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(
                isBook ? borderRadius - 4 : 0,
              ),
              child: OmniCachedImage(
                imageUrl: imageUrl,
                fit: isBook ? BoxFit.contain : BoxFit.cover,
                fallback: _ArtworkFallback(type: item.type),
                memCacheWidth: memCacheWidth,
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
                    Colors.transparent,
                    Colors.black.withValues(
                      alpha: item.type == 'book' ? 0 : 0.22,
                    ),
                  ],
                ),
              ),
            ),
          ),
          if (grouped)
            Positioned(
              left: 8,
              bottom: 8,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.62),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(
                    color: AppTheme.ink.withValues(alpha: 0.08),
                  ),
                ),
                child: const Text(
                  'Album',
                  style: TextStyle(
                    color: AppTheme.ink,
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _ArtworkFallback extends StatelessWidget {
  final String type;

  const _ArtworkFallback({required this.type});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppTheme.surfaceAlt,
      alignment: Alignment.center,
      child: Icon(
        _icon(type),
        color: AppTheme.ink.withValues(alpha: 0.3),
        size: 36,
      ),
    );
  }

  IconData _icon(String type) {
    switch (type) {
      case 'movie':
        return Icons.movie_outlined;
      case 'book':
        return Icons.menu_book_outlined;
      default:
        return CupertinoIcons.music_note;
    }
  }
}
