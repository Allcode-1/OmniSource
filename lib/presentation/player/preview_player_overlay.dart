import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:youtube_player_iframe/youtube_player_iframe.dart';

import '../../core/theme/app_theme.dart';
import '../widgets/content_artwork.dart';
import 'preview_player_controller.dart';

class PreviewPlayerOverlay extends StatefulWidget {
  final Widget child;

  const PreviewPlayerOverlay({super.key, required this.child});

  @override
  State<PreviewPlayerOverlay> createState() => _PreviewPlayerOverlayState();
}

class _PreviewPlayerOverlayState extends State<PreviewPlayerOverlay> {
  final PreviewPlayerController _controller = PreviewPlayerController.instance;
  Offset? _videoOffset;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        return Stack(
          children: [
            widget.child,
            if (_controller.mode == PreviewPlayerMode.audio)
              _AudioMiniPlayer(controller: _controller),
            if (_controller.mode == PreviewPlayerMode.video)
              _VideoMiniPlayer(
                controller: _controller,
                offset: _videoOffset,
                onDrag: (delta, size) {
                  setState(() {
                    final current =
                        _videoOffset ?? _defaultVideoOffset(context);
                    _videoOffset = _clampVideoOffset(
                      current + delta,
                      context,
                      size,
                    );
                  });
                },
              ),
          ],
        );
      },
    );
  }

  Offset _defaultVideoOffset(BuildContext context) {
    final media = MediaQuery.of(context);
    final width = media.size.width;
    final playerWidth = _videoWidth(width);
    return Offset(width - playerWidth - 14, media.padding.top + 12);
  }

  Offset _clampVideoOffset(Offset value, BuildContext context, Size size) {
    final media = MediaQuery.of(context);
    final maxX = media.size.width - size.width - 10;
    final maxY = media.size.height - size.height - media.padding.bottom - 14;
    return Offset(
      value.dx.clamp(10.0, maxX.clamp(10.0, double.infinity)),
      value.dy.clamp(media.padding.top + 8, maxY.clamp(10.0, double.infinity)),
    );
  }

  double _videoWidth(double screenWidth) {
    return screenWidth < 420 ? screenWidth - 28 : 330;
  }
}

class _AudioMiniPlayer extends StatelessWidget {
  final PreviewPlayerController controller;

  const _AudioMiniPlayer({required this.controller});

  @override
  Widget build(BuildContext context) {
    final item = controller.item;
    final preview = controller.preview;
    if (item == null || preview == null) return const SizedBox.shrink();

    final progress = controller.audioDuration.inMilliseconds <= 0
        ? 0.0
        : controller.audioPosition.inMilliseconds /
              controller.audioDuration.inMilliseconds;

    return Positioned(
      left: 12,
      right: 12,
      bottom: MediaQuery.paddingOf(context).bottom + 78,
      child: Material(
        color: Colors.transparent,
        child: Container(
          clipBehavior: Clip.antiAlias,
          decoration: BoxDecoration(
            color: AppTheme.surfaceAlt.withValues(alpha: 0.98),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: AppTheme.ink.withValues(alpha: 0.08)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.35),
                blurRadius: 24,
                offset: const Offset(0, 12),
              ),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(10, 10, 8, 9),
                child: Row(
                  children: [
                    SizedBox(
                      width: 46,
                      height: 46,
                      child: ContentArtwork(
                        item: item,
                        borderRadius: 10,
                        memCacheWidth: 180,
                      ),
                    ),
                    const SizedBox(width: 11),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            item.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: AppTheme.ink,
                              fontSize: 14,
                              fontWeight: FontWeight.w700,
                              height: 1.1,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            preview.provider,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: AppTheme.ink.withValues(alpha: 0.5),
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    ),
                    _MiniIconButton(
                      icon: controller.isAudioPlaying
                          ? CupertinoIcons.pause_fill
                          : CupertinoIcons.play_fill,
                      onTap: controller.toggleAudio,
                    ),
                    _MiniIconButton(
                      icon: CupertinoIcons.xmark,
                      onTap: controller.closePlayer,
                    ),
                  ],
                ),
              ),
              LinearProgressIndicator(
                minHeight: 2,
                value: progress.clamp(0.0, 1.0),
                backgroundColor: AppTheme.ink.withValues(alpha: 0.08),
                color: AppTheme.primary,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _VideoMiniPlayer extends StatelessWidget {
  final PreviewPlayerController controller;
  final Offset? offset;
  final void Function(Offset delta, Size size) onDrag;

  const _VideoMiniPlayer({
    required this.controller,
    required this.offset,
    required this.onDrag,
  });

  @override
  Widget build(BuildContext context) {
    final youtube = controller.youtubeController;
    final preview = controller.preview;
    if (youtube == null || preview == null) return const SizedBox.shrink();

    final media = MediaQuery.of(context);
    final width = media.size.width < 420 ? media.size.width - 28 : 330.0;
    final height = (width / (16 / 9)) + 42;
    final topLeft =
        offset ?? Offset(media.size.width - width - 14, media.padding.top + 12);
    final size = Size(width, height);

    return Positioned(
      left: topLeft.dx,
      top: topLeft.dy,
      width: width,
      child: Material(
        color: Colors.transparent,
        child: GestureDetector(
          onPanUpdate: (details) => onDrag(details.delta, size),
          child: Container(
            clipBehavior: Clip.antiAlias,
            decoration: BoxDecoration(
              color: AppTheme.surfaceAlt.withValues(alpha: 0.98),
              borderRadius: BorderRadius.circular(18),
              border: Border.all(color: AppTheme.ink.withValues(alpha: 0.1)),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.38),
                  blurRadius: 28,
                  offset: const Offset(0, 14),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  height: width / (16 / 9),
                  child: YoutubePlayer(
                    controller: youtube,
                    aspectRatio: 16 / 9,
                  ),
                ),
                SizedBox(
                  height: 42,
                  child: Row(
                    children: [
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          preview.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: AppTheme.ink,
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      _MiniIconButton(
                        icon: CupertinoIcons.xmark,
                        onTap: controller.closePlayer,
                      ),
                      const SizedBox(width: 4),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _MiniIconButton extends StatelessWidget {
  final IconData icon;
  final Future<void> Function() onTap;

  const _MiniIconButton({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: SizedBox(
        width: 40,
        height: 40,
        child: Icon(icon, color: AppTheme.ink, size: 20),
      ),
    );
  }
}
