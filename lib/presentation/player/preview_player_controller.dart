import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:youtube_player_iframe/youtube_player_iframe.dart'
    hide PlayerState;

import '../../domain/entities/content_preview.dart';
import '../../domain/entities/unified_content.dart';

enum PreviewPlayerMode { hidden, audio, video }

class PreviewPlayerController extends ChangeNotifier {
  PreviewPlayerController._() {
    _audioPlayer.onPlayerStateChanged.listen((state) {
      isAudioPlaying = state == PlayerState.playing;
      notifyListeners();
    });
    _audioPlayer.onPositionChanged.listen((value) {
      audioPosition = value;
      notifyListeners();
    });
    _audioPlayer.onDurationChanged.listen((value) {
      audioDuration = value;
      notifyListeners();
    });
    _audioPlayer.onPlayerComplete.listen((_) {
      isAudioPlaying = false;
      _audioStarted = false;
      audioPosition = Duration.zero;
      notifyListeners();
    });
  }

  static final PreviewPlayerController instance = PreviewPlayerController._();

  final AudioPlayer _audioPlayer = AudioPlayer();

  PreviewPlayerMode mode = PreviewPlayerMode.hidden;
  UnifiedContent? item;
  ContentPreview? preview;
  YoutubePlayerController? youtubeController;
  bool isAudioPlaying = false;
  bool _audioStarted = false;
  Duration audioPosition = Duration.zero;
  Duration audioDuration = Duration.zero;

  Future<void> showAudio({
    required UnifiedContent item,
    required ContentPreview preview,
  }) async {
    await _closeYoutube();
    await _audioPlayer.stop();
    this.item = item;
    this.preview = preview;
    mode = PreviewPlayerMode.audio;
    isAudioPlaying = false;
    _audioStarted = false;
    audioPosition = Duration.zero;
    audioDuration = Duration.zero;
    notifyListeners();
  }

  Future<void> toggleAudio() async {
    if (mode != PreviewPlayerMode.audio) return;
    if (isAudioPlaying) {
      await _audioPlayer.pause();
    } else {
      final audioPreview = preview;
      if (audioPreview == null) return;
      if (_audioStarted) {
        await _audioPlayer.resume();
      } else {
        _audioStarted = true;
        await _audioPlayer.play(UrlSource(audioPreview.url));
      }
    }
  }

  Future<bool> showVideo({
    required UnifiedContent item,
    required ContentPreview preview,
  }) async {
    final videoId = _videoIdFor(preview);
    if (videoId == null) return false;

    await _audioPlayer.stop();
    await _closeYoutube();
    this.item = item;
    this.preview = preview;
    youtubeController = YoutubePlayerController.fromVideoId(
      videoId: videoId,
      autoPlay: false,
      params: const YoutubePlayerParams(
        showControls: true,
        showFullscreenButton: true,
        playsInline: true,
        enableCaption: true,
        strictRelatedVideos: true,
      ),
    );
    mode = PreviewPlayerMode.video;
    notifyListeners();
    return true;
  }

  Future<void> closePlayer() async {
    await _audioPlayer.stop();
    await _closeYoutube();
    mode = PreviewPlayerMode.hidden;
    item = null;
    preview = null;
    isAudioPlaying = false;
    _audioStarted = false;
    audioPosition = Duration.zero;
    audioDuration = Duration.zero;
    notifyListeners();
  }

  Future<void> _closeYoutube() async {
    final controller = youtubeController;
    youtubeController = null;
    if (controller != null) {
      await controller.close();
    }
  }

  String? _videoIdFor(ContentPreview preview) {
    final urls = [
      preview.embedUrl,
      preview.url,
      preview.externalUrl,
    ].whereType<String>();

    for (final url in urls) {
      final manualId = _extractYoutubeId(url);
      if (manualId != null) return manualId;
      final convertedId = YoutubePlayerController.convertUrlToId(url);
      if (convertedId != null) return convertedId;
    }
    return null;
  }

  String? _extractYoutubeId(String rawUrl) {
    final uri = Uri.tryParse(rawUrl.trim());
    if (uri == null) return null;

    final host = uri.host.toLowerCase();
    if (host == 'youtu.be') {
      return _validYoutubeId(
        uri.pathSegments.isEmpty ? null : uri.pathSegments.first,
      );
    }

    if (!host.contains('youtube.com')) return null;
    final watchId = _validYoutubeId(uri.queryParameters['v']);
    if (watchId != null) return watchId;

    final segments = uri.pathSegments;
    for (var index = 0; index < segments.length - 1; index++) {
      final marker = segments[index].toLowerCase();
      if (marker == 'embed' || marker == 'shorts' || marker == 'live') {
        return _validYoutubeId(segments[index + 1]);
      }
    }
    return null;
  }

  String? _validYoutubeId(String? value) {
    final id = value?.trim();
    if (id == null || id.isEmpty) return null;
    final match = RegExp(r'^[A-Za-z0-9_-]{11}$').firstMatch(id);
    return match == null ? null : id;
  }
}
