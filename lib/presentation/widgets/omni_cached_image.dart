import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/widgets.dart';

import '../../core/constants/api_constants.dart';

class OmniCachedImage extends StatelessWidget {
  final String imageUrl;
  final BoxFit fit;
  final Widget fallback;
  final Duration fadeInDuration;
  final int? memCacheWidth;
  final int? memCacheHeight;

  const OmniCachedImage({
    super.key,
    required this.imageUrl,
    required this.fallback,
    this.fit = BoxFit.cover,
    this.fadeInDuration = const Duration(milliseconds: 120),
    this.memCacheWidth,
    this.memCacheHeight,
  });

  @override
  Widget build(BuildContext context) {
    final url = imageUrl.trim();
    if (url.isEmpty) return fallback;
    final originalUrl = ApiConstants.unwrapImageProxyUrl(url);
    return CachedNetworkImage(
      imageUrl: url,
      fit: fit,
      fadeInDuration: fadeInDuration,
      memCacheWidth: memCacheWidth,
      memCacheHeight: memCacheHeight,
      placeholder: (context, url) => fallback,
      errorWidget: (context, url, error) {
        if (originalUrl == url || originalUrl.isEmpty) return fallback;
        return CachedNetworkImage(
          imageUrl: originalUrl,
          fit: fit,
          fadeInDuration: fadeInDuration,
          memCacheWidth: memCacheWidth,
          memCacheHeight: memCacheHeight,
          placeholder: (context, url) => fallback,
          errorWidget: (context, url, error) => fallback,
        );
      },
    );
  }
}
