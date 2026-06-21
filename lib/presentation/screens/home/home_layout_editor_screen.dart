import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/storage/home_layout_prefs.dart';

class HomeLayoutEditorScreen extends StatefulWidget {
  final List<String> availableSections;
  final HomeLayoutConfig initialConfig;

  const HomeLayoutEditorScreen({
    super.key,
    required this.availableSections,
    required this.initialConfig,
  });

  @override
  State<HomeLayoutEditorScreen> createState() => _HomeLayoutEditorScreenState();
}

class _HomeLayoutEditorScreenState extends State<HomeLayoutEditorScreen> {
  late final List<String> _orderedSections;
  late final Set<String> _hiddenSections;

  @override
  void initState() {
    super.initState();
    _orderedSections = _buildInitialOrder();
    _hiddenSections = {...widget.initialConfig.hiddenSections};
  }

  List<String> _buildInitialOrder() {
    final base = <String>[];
    for (final section in widget.initialConfig.orderedSections) {
      if (widget.availableSections.contains(section) &&
          !base.contains(section)) {
        base.add(section);
      }
    }
    for (final section in widget.availableSections) {
      if (!base.contains(section)) {
        base.add(section);
      }
    }
    return base;
  }

  void _onReorder(int oldIndex, int newIndex) {
    setState(() {
      final moved = _orderedSections.removeAt(oldIndex);
      _orderedSections.insert(newIndex, moved);
    });
  }

  void _toggleVisibility(String section, bool visible) {
    setState(() {
      if (visible) {
        _hiddenSections.remove(section);
      } else {
        _hiddenSections.add(section);
      }
    });
  }

  void _save() {
    Navigator.pop(
      context,
      HomeLayoutConfig(
        orderedSections: _orderedSections,
        hiddenSections: _hiddenSections,
      ),
    );
  }

  void _reset() {
    setState(() {
      _orderedSections
        ..clear()
        ..addAll(widget.availableSections);
      _hiddenSections.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        foregroundColor: Colors.white,
        title: const Text(
          'Home Layout Editor',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
        actions: [
          TextButton(
            onPressed: _reset,
            style: TextButton.styleFrom(foregroundColor: Colors.white70),
            child: const Text('Reset'),
          ),
          TextButton(
            onPressed: _save,
            style: TextButton.styleFrom(foregroundColor: AppTheme.primary),
            child: const Text('Save'),
          ),
        ],
      ),
      body: ReorderableListView.builder(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 120),
        itemCount: _orderedSections.length,
        onReorderItem: _onReorder,
        buildDefaultDragHandles: false,
        itemBuilder: (context, index) {
          final section = _orderedSections[index];
          final visible = !_hiddenSections.contains(section);
          return Container(
            key: ValueKey(section),
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: Theme.of(
                context,
              ).colorScheme.surface.withValues(alpha: 0.94),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.white.withValues(alpha: 0.07)),
            ),
            child: Row(
              children: [
                ReorderableDragStartListener(
                  index: index,
                  child: const Padding(
                    padding: EdgeInsets.only(right: 10),
                    child: Icon(CupertinoIcons.line_horizontal_3),
                  ),
                ),
                Expanded(
                  child: Text(
                    section,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                CupertinoSwitch(
                  value: visible,
                  onChanged: (value) => _toggleVisibility(section, value),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
