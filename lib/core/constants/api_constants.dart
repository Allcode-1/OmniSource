import 'package:flutter/foundation.dart';

class ApiConstants {
  static const String configuredBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://5.42.108.117/api',
  );
  static const bool useImageProxy = bool.fromEnvironment(
    'USE_IMAGE_PROXY',
    defaultValue: true,
  );

  static String get baseUrl {
    final configured = configuredBaseUrl.endsWith('/')
        ? configuredBaseUrl.substring(0, configuredBaseUrl.length - 1)
        : configuredBaseUrl;
    final isLocalhost =
        configured.contains('://localhost') ||
        configured.contains('://127.0.0.1');
    if (!kIsWeb &&
        defaultTargetPlatform == TargetPlatform.android &&
        isLocalhost) {
      return configured
          .replaceFirst('://localhost', '://10.0.2.2')
          .replaceFirst('://127.0.0.1', '://10.0.2.2');
    }
    return configured;
  }

  // Auth
  static const String login = "/auth/login";
  static const String register = "/auth/register";
  static const String refresh = "/auth/refresh";
  static const String logout = "/auth/logout";

  static const String userMe = '/user/me';
  static const String userUpdate = '/user/update';
  static const String userDelete = '/user/me';

  // Discovery
  static const String search = "/content/search";

  // Actions (users library)
  static const String favorites = "/actions/favorites";
  static const String like = "/actions/like";
  static const String playlists = "/actions/playlists";

  // Content
  static const String trending = "/content/trending";
  static const String home = "/content/home";
  static const String recommendations = "/content/recommendations";
  static const String preview = "/content/preview";

  // Research
  static const String deepResearch = "/research/deep";

  static String resolveImageUrl(String? rawUrl) {
    if (rawUrl == null) return '';
    final value = rawUrl.trim();
    if (value.isEmpty) return '';
    if (!useImageProxy || !value.startsWith('http')) return value;
    if (value.contains('/content/image-proxy?url=')) return value;
    return '$baseUrl/content/image-proxy?url=${Uri.encodeQueryComponent(value)}';
  }
}
