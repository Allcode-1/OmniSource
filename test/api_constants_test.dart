import 'package:flutter_test/flutter_test.dart';
import 'package:omnisource/core/constants/api_constants.dart';

void main() {
  group('ApiConstants.resolveImageUrl', () {
    test('returns empty for null/blank', () {
      expect(ApiConstants.resolveImageUrl(null), isEmpty);
      expect(ApiConstants.resolveImageUrl('   '), isEmpty);
    });

    test('keeps non-http urls untouched', () {
      expect(
        ApiConstants.resolveImageUrl('/assets/cover.jpg'),
        '/assets/cover.jpg',
      );
    });

    test('keeps already proxied urls untouched', () {
      final proxied =
          '${ApiConstants.baseUrl}/content/image-proxy?url=https://x';
      expect(ApiConstants.resolveImageUrl(proxied), proxied);
    });

    test('wraps external image with proxy url when proxy enabled', () {
      final resolved = ApiConstants.resolveImageUrl(
        'https://image.tmdb.org/t/p/w500/a.jpg',
      );
      expect(resolved, contains('/content/image-proxy?url='));
      expect(resolved, startsWith(ApiConstants.baseUrl));
    });

    test('unwraps an image proxy url back to the original source', () {
      const original = 'https://image.tmdb.org/t/p/w500/a.jpg';
      final proxied = ApiConstants.resolveImageUrl(original);

      expect(ApiConstants.unwrapImageProxyUrl(proxied), original);
      expect(ApiConstants.unwrapImageProxyUrl(original), original);
    });
  });
}
