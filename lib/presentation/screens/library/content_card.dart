import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/utils/content_display.dart';
import '../../../domain/entities/unified_content.dart';
import '../../../domain/repositories/analytics_repository.dart';
import '../../bloc/library/library_cubit.dart';
import '../../bloc/library/library_state.dart';
import '../../widgets/content_artwork.dart';
import '../../widgets/content_quick_actions.dart';
import '../home/detail_screen.dart';

class ContentCard extends StatelessWidget {
  final UnifiedContent item;
  final List<UnifiedContent> groupedItems;

  const ContentCard({
    super.key,
    required this.item,
    this.groupedItems = const [],
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cluster = ContentCluster(
      primary: item,
      items: groupedItems.isEmpty ? [item] : groupedItems,
    );

    return BlocBuilder<LibraryCubit, LibraryState>(
      builder: (context, state) {
        final isLiked = state is LibraryLoaded
            ? state.favorites.any((fav) => fav.externalId == item.externalId)
            : false;

        return GestureDetector(
          onLongPress: () =>
              ContentQuickActions.show(context, item, source: 'library'),
          onTap: () {
            context.read<AnalyticsRepository>().trackEvent(
              type: 'view',
              extId: item.externalId,
              contentType: item.type,
              meta: {
                'source': 'library_content_card',
                'title': item.title,
                'image_url': item.imageUrl,
                'rating': item.rating,
                'release_date': item.releaseDate,
                'genres': item.genres,
                'grouped_count': cluster.trackCount,
              },
            );
            Navigator.push(
              context,
              CupertinoPageRoute(
                builder: (_) =>
                    DetailScreen(content: item, groupedItems: cluster.items),
              ),
            );
          },
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AspectRatio(
                aspectRatio: ContentArtwork.aspectRatioFor(item.type),
                child: Stack(
                  children: [
                    Positioned.fill(
                      child: ContentArtwork(
                        item: item,
                        grouped: cluster.isMusicAlbumGroup,
                        memCacheWidth: 480,
                      ),
                    ),
                    Positioned(
                      top: 8,
                      right: 8,
                      child: _CircleAction(
                        icon: PhosphorIcons.heart(
                          isLiked
                              ? PhosphorIconsStyle.fill
                              : PhosphorIconsStyle.regular,
                        ),
                        iconColor: isLiked
                            ? const Color(0xFFFF5D73)
                            : Colors.white,
                        onTap: () =>
                            context.read<LibraryCubit>().toggleFavorite(item),
                      ),
                    ),
                    if (cluster.isMusicAlbumGroup)
                      Positioned(
                        right: 8,
                        bottom: 8,
                        child: _CountBadge(count: cluster.trackCount),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              Text(
                cluster.displayTitle,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 2),
              Row(
                children: [
                  Text(
                    contentTypeLabel(item.type),
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: Colors.white.withValues(alpha: 0.62),
                      fontWeight: FontWeight.w600,
                      fontSize: 11,
                    ),
                  ),
                  if (item.rating > 0) ...[
                    const SizedBox(width: 6),
                    Text(
                      '- ${item.rating.toStringAsFixed(1)}',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: Colors.white.withValues(alpha: 0.48),
                        fontSize: 11,
                      ),
                    ),
                  ],
                ],
              ),
              if (cluster.displaySubtitle().isNotEmpty)
                Text(
                  cluster.displaySubtitle(),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: Colors.white.withValues(alpha: 0.46),
                    fontSize: 12,
                  ),
                ),
            ],
          ),
        );
      },
    );
  }
}

class _CircleAction extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final VoidCallback onTap;

  const _CircleAction({
    required this.icon,
    this.iconColor = Colors.white,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(6),
        decoration: const BoxDecoration(
          color: Color(0x66000000),
          shape: BoxShape.circle,
        ),
        child: Icon(icon, size: 17, color: iconColor),
      ),
    );
  }
}

class _CountBadge extends StatelessWidget {
  final int count;

  const _CountBadge({required this.count});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.62),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppTheme.ink.withValues(alpha: 0.08)),
      ),
      child: Text(
        '$count tracks',
        style: const TextStyle(
          color: AppTheme.ink,
          fontSize: 10,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
