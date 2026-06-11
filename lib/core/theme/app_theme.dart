import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  static const primary = Color(0xFF0984E3);
  static const secondary = Color(0xFFA1A1A6);
  static const ink = Color(0xFFF5F5F7);
  static const authBackground = Color(0xFF000000);
  static const appBackground = Color(0xFF000000);
  static const surface = Color(0xFF1C1C1E);
  static const surfaceAlt = Color(0xFF2C2C2E);
  static const line = Color(0xFF2A2A2D);

  static ThemeData get authTheme => _buildTheme(
    scaffoldColor: authBackground,
    inputFill: const Color(0xFF151515),
  );

  static ThemeData get mainTheme =>
      _buildTheme(scaffoldColor: Colors.transparent, inputFill: surface);

  static BoxDecoration get mainBackgroundDecoration =>
      const BoxDecoration(color: appBackground);

  static ThemeData _buildTheme({
    required Color scaffoldColor,
    required Color inputFill,
  }) {
    final base = ThemeData.dark();
    final colorScheme = const ColorScheme.dark(
      primary: primary,
      secondary: secondary,
      surface: surface,
      error: Color(0xFFFF6B6B),
      onPrimary: ink,
      onSecondary: ink,
      onSurface: ink,
    );

    final textTheme = GoogleFonts.interTextTheme(base.textTheme).copyWith(
      displayMedium: GoogleFonts.inter(
        fontWeight: FontWeight.w700,
        letterSpacing: 0,
        color: ink,
      ),
      headlineSmall: GoogleFonts.inter(
        fontWeight: FontWeight.w600,
        letterSpacing: 0,
        color: ink,
      ),
      titleLarge: GoogleFonts.inter(fontWeight: FontWeight.w500, color: ink),
      titleMedium: GoogleFonts.inter(fontWeight: FontWeight.w500, color: ink),
      bodyLarge: GoogleFonts.inter(
        fontWeight: FontWeight.w400,
        color: ink.withValues(alpha: 0.95),
      ),
      bodyMedium: GoogleFonts.inter(
        fontWeight: FontWeight.w400,
        color: ink.withValues(alpha: 0.86),
      ),
      labelLarge: GoogleFonts.inter(
        fontWeight: FontWeight.w500,
        letterSpacing: 0,
        color: ink,
      ),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: colorScheme,
      primaryColor: primary,
      scaffoldBackgroundColor: scaffoldColor,
      cardColor: surface,
      dividerColor: line,
      textTheme: textTheme,
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        toolbarHeight: 64,
        titleSpacing: 20,
        actionsPadding: const EdgeInsets.only(right: 8),
        titleTextStyle: textTheme.titleLarge?.copyWith(
          fontSize: 24,
          color: ink,
        ),
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          padding: const EdgeInsets.all(10),
          minimumSize: const Size(44, 44),
          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: inputFill,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 14,
          vertical: 14,
        ),
        hintStyle: TextStyle(color: Colors.white.withValues(alpha: 0.45)),
        helperStyle: const TextStyle(fontSize: 10),
        errorStyle: const TextStyle(fontSize: 10, color: Color(0xFFFF6B6B)),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: line),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.08)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: primary, width: 1.3),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: ink,
          elevation: 0,
          minimumSize: const Size(0, 52),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
          textStyle: textTheme.labelLarge?.copyWith(fontSize: 14),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: ink,
          side: BorderSide(color: ink.withValues(alpha: 0.12)),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          textStyle: textTheme.labelLarge?.copyWith(fontSize: 13),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: surface,
        selectedColor: primary.withValues(alpha: 0.18),
        labelStyle: textTheme.bodySmall ?? const TextStyle(color: ink),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        side: BorderSide(color: Colors.white.withValues(alpha: 0.08)),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 0),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: surfaceAlt,
        contentTextStyle: textTheme.bodyMedium?.copyWith(color: ink),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      listTileTheme: ListTileThemeData(
        iconColor: ink.withValues(alpha: 0.9),
        textColor: ink,
        tileColor: surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: surface,
        surfaceTintColor: Colors.transparent,
      ),
      dividerTheme: DividerThemeData(
        color: ink.withValues(alpha: 0.08),
        thickness: 1,
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(color: primary),
      pageTransitionsTheme: const PageTransitionsTheme(
        builders: {
          TargetPlatform.android: CupertinoPageTransitionsBuilder(),
          TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
          TargetPlatform.windows: CupertinoPageTransitionsBuilder(),
          TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
          TargetPlatform.linux: CupertinoPageTransitionsBuilder(),
        },
      ),
    );
  }
}
