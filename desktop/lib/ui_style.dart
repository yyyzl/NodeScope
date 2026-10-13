import 'dart:io';

import 'package:flutter/material.dart';

const cream = Color(0xfffefcf6);
const paper = Color(0xfffffcf7);
const ink = Color(0xff1a1a2e);
const muted = Color(0xff666876);
const border = Color(0xffe5e2d9);
const blue = Color(0xff2472c2);
const blueTint = Color(0xffedf4fd);
const yellowTint = Color(0xfffff2b5);
const green = Color(0xff2d6a4f);
const red = Color(0xffb3364b);

TextStyle heading(double size) => TextStyle(
  fontSize: size,
  color: ink,
  fontWeight: FontWeight.w700,
  fontFamily: Platform.isWindows ? 'SimSun' : 'Songti SC',
  height: 1.35,
);

ThemeData probeTheme() => ThemeData(
  useMaterial3: true,
  visualDensity: VisualDensity.compact,
  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
  scaffoldBackgroundColor: cream,
  fontFamily: Platform.isWindows ? 'Microsoft YaHei' : 'PingFang SC',
  colorScheme: ColorScheme.fromSeed(
    seedColor: blue,
    surface: cream,
    primary: blue,
    onSurface: ink,
  ),
  textTheme: const TextTheme(
    bodyLarge: TextStyle(fontSize: 14, color: ink, height: 1.5),
    bodyMedium: TextStyle(fontSize: 14, color: ink, height: 1.55),
  ),
  inputDecorationTheme: InputDecorationTheme(
    isDense: true,
    filled: true,
    fillColor: paper,
    contentPadding: const EdgeInsets.symmetric(horizontal: 11, vertical: 11),
    hintStyle: const TextStyle(fontSize: 13, color: muted),
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(7),
      borderSide: const BorderSide(color: border),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(7),
      borderSide: const BorderSide(color: Color(0xffd6d3cb)),
    ),
  ),
  filledButtonTheme: FilledButtonThemeData(
    style: FilledButton.styleFrom(
      backgroundColor: blue,
      foregroundColor: cream,
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(7)),
      padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 14),
    ),
  ),
  outlinedButtonTheme: OutlinedButtonThemeData(
    style: OutlinedButton.styleFrom(
      foregroundColor: ink,
      backgroundColor: paper,
      side: const BorderSide(color: border),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(7)),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 13),
    ),
  ),
  textButtonTheme: TextButtonThemeData(
    style: TextButton.styleFrom(
      foregroundColor: blue,
      textStyle: const TextStyle(fontSize: 13),
    ),
  ),
  dividerTheme: const DividerThemeData(color: border, thickness: 1),
  checkboxTheme: CheckboxThemeData(
    fillColor: WidgetStateProperty.resolveWith(
      (s) => s.contains(WidgetState.selected) ? blue : null,
    ),
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(3)),
  ),
  dialogTheme: DialogThemeData(
    backgroundColor: cream,
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
  ),
);

class LabeledField extends StatelessWidget {
  final String label;
  final Widget child;
  final String? hint;
  const LabeledField({
    super.key,
    required this.label,
    required this.child,
    this.hint,
  });
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 14),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontWeight: FontWeight.w500)),
        const SizedBox(height: 7),
        child,
        if (hint != null)
          Padding(
            padding: const EdgeInsets.only(top: 5),
            child: Text(
              hint!,
              style: const TextStyle(fontSize: 13, color: muted),
            ),
          ),
      ],
    ),
  );
}

class DialogShell extends StatelessWidget {
  final String title;
  final Widget child;
  final List<Widget> actions;
  final double width;
  const DialogShell({
    super.key,
    required this.title,
    required this.child,
    required this.actions,
    this.width = 620,
  });
  @override
  Widget build(BuildContext context) => Dialog(
    insetPadding: const EdgeInsets.all(24),
    child: ConstrainedBox(
      constraints: BoxConstraints(
        maxWidth: width,
        maxHeight: MediaQuery.sizeOf(context).height - 48,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 16, 12, 14),
            child: Row(
              children: [
                Expanded(child: Text(title, style: heading(22))),
                IconButton(
                  tooltip: '关闭',
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.close, size: 20),
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          Flexible(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: child,
            ),
          ),
          const Divider(height: 1),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Wrap(
              alignment: WrapAlignment.end,
              spacing: 10,
              runSpacing: 8,
              children: actions,
            ),
          ),
        ],
      ),
    ),
  );
}

String formatMs(dynamic number) =>
    number is num ? '${number.toStringAsFixed(1)} ms' : '—';
