import 'package:flutter/material.dart';
import 'package:omnisource/core/theme/app_theme.dart';
import 'package:omnisource/presentation/screens/deep_research/deep_research_screen.dart';
import 'package:omnisource/presentation/screens/home/home_screen.dart';
import 'package:omnisource/presentation/screens/library/library_screen.dart';
import 'package:omnisource/presentation/screens/search/search_screen.dart';

class MainLayout extends StatefulWidget {
  const MainLayout({super.key});

  @override
  State<MainLayout> createState() => _MainLayoutState();
}

class _MainLayoutState extends State<MainLayout> {
  int _currentIndex = 0;

  final List<Widget> _screens = [
    const HomeScreen(),
    const DeepResearchScreen(),
    const LibraryScreen(),
    const SearchScreen(),
  ];

  static const _items = <_NavItem>[
    _NavItem(icon: Icons.home_outlined, activeIcon: Icons.home, label: 'Home'),
    _NavItem(
      icon: Icons.auto_awesome_outlined,
      activeIcon: Icons.auto_awesome,
      label: 'Discover',
    ),
    _NavItem(
      icon: Icons.library_books_outlined,
      activeIcon: Icons.library_books,
      label: 'Library',
    ),
    _NavItem(icon: Icons.search, activeIcon: Icons.search, label: 'Search'),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBody: false,
      body: IndexedStack(index: _currentIndex, children: _screens),
      bottomNavigationBar: DecoratedBox(
        decoration: BoxDecoration(
          color: const Color(0xFF090909).withValues(alpha: 0.98),
          border: Border(
            top: BorderSide(color: AppTheme.ink.withValues(alpha: 0.08)),
          ),
        ),
        child: SafeArea(
          top: false,
          child: SizedBox(
            height: 66,
            child: Row(
              children: List.generate(_items.length, (index) {
                final item = _items[index];
                final selected = _currentIndex == index;
                final color = selected
                    ? AppTheme.primary
                    : AppTheme.ink.withValues(alpha: 0.52);

                return Expanded(
                  child: GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTap: () => setState(() => _currentIndex = index),
                    child: Tooltip(
                      message: item.label,
                      child: Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              selected ? item.activeIcon : item.icon,
                              size: selected ? 24 : 23,
                              color: color,
                            ),
                            const SizedBox(height: 4),
                            Text(
                              item.label,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                color: color,
                                fontSize: 10,
                                fontWeight: selected
                                    ? FontWeight.w700
                                    : FontWeight.w500,
                                height: 1,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                );
              }),
            ),
          ),
        ),
      ),
    );
  }
}

class _NavItem {
  final IconData icon;
  final IconData activeIcon;
  final String label;

  const _NavItem({
    required this.icon,
    required this.activeIcon,
    required this.label,
  });
}
