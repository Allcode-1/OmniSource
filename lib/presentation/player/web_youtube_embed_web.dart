import 'dart:ui_web' as ui_web;

import 'package:flutter/widgets.dart';
import 'package:web/web.dart' as web;

class WebYoutubeEmbed extends StatefulWidget {
  final String videoId;

  const WebYoutubeEmbed({super.key, required this.videoId});

  @override
  State<WebYoutubeEmbed> createState() => _WebYoutubeEmbedState();
}

class _WebYoutubeEmbedState extends State<WebYoutubeEmbed> {
  static int _nextViewId = 0;

  late final String _viewType;
  late final web.HTMLIFrameElement _iframe;

  @override
  void initState() {
    super.initState();
    _viewType = 'omni-youtube-embed-${_nextViewId++}';
    _iframe = web.HTMLIFrameElement()
      ..style.width = '100%'
      ..style.height = '100%'
      ..style.border = '0'
      ..style.display = 'block';
    _iframe
      ..setAttribute(
        'allow',
        'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share',
      )
      ..setAttribute('allowfullscreen', 'true')
      ..setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
    _setSource(widget.videoId);
    ui_web.platformViewRegistry.registerViewFactory(_viewType, (_) => _iframe);
  }

  @override
  void didUpdateWidget(covariant WebYoutubeEmbed oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.videoId != widget.videoId) {
      _setSource(widget.videoId);
    }
  }

  void _setSource(String videoId) {
    final origin = Uri.base.origin;
    final params = Uri(
      queryParameters: {
        'playsinline': '1',
        'rel': '0',
        'modestbranding': '1',
        'enablejsapi': '0',
        'origin': origin,
      },
    ).query;
    _iframe.src = 'https://www.youtube.com/embed/$videoId?$params';
  }

  @override
  Widget build(BuildContext context) {
    return HtmlElementView(viewType: _viewType);
  }
}
