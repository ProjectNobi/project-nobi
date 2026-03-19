/**
 * Memory display card component.
 * Shows memory content with type icon, tags, and delete action.
 */

import React, { useCallback } from 'react';
import { View, Text, StyleSheet, Pressable, Alert } from 'react-native';
import { theme } from '../styles/theme';
import type { Memory } from '../services/api';

// ─── Props ───────────────────────────────────────────────────────────────────

interface MemoryCardProps {
  memory: Memory;
  onDelete: (id: string) => void;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const TYPE_ICONS: Record<Memory['type'], string> = {
  fact: '📌',
  preference: '❤️',
  event: '📅',
  context: '💭',
  emotion: '😊',
};

const TYPE_LABELS: Record<Memory['type'], string> = {
  fact: 'Fact',
  preference: 'Preference',
  event: 'Event',
  context: 'Context',
  emotion: 'Emotion',
};

// ─── Component ───────────────────────────────────────────────────────────────

export function MemoryCard({ memory, onDelete }: MemoryCardProps) {
  const icon = TYPE_ICONS[memory.type] ?? '📝';
  const label = TYPE_LABELS[memory.type] ?? memory.type;

  const handleDelete = useCallback(() => {
    Alert.alert(
      'Delete Memory',
      'Are you sure you want to delete this memory?',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: () => onDelete(memory.id) },
      ],
    );
  }, [memory.id, onDelete]);

  const formatDate = (dateStr: string): string => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <View style={styles.card}>
      {/* Header: type + delete */}
      <View style={styles.header}>
        <View style={styles.typeContainer}>
          <Text style={styles.icon}>{icon}</Text>
          <Text style={styles.typeLabel}>{label}</Text>
        </View>
        <Pressable onPress={handleDelete} hitSlop={8}>
          <Text style={styles.deleteButton}>🗑️</Text>
        </Pressable>
      </View>

      {/* Content */}
      <Text style={styles.content}>{memory.content}</Text>

      {/* Tags */}
      {memory.tags.length > 0 && (
        <View style={styles.tagsContainer}>
          {memory.tags.map((tag) => (
            <View key={tag} style={styles.tag}>
              <Text style={styles.tagText}>#{tag}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Footer: date + importance */}
      <View style={styles.footer}>
        <Text style={styles.date}>{formatDate(memory.createdAt)}</Text>
        {memory.importance > 0.7 && <Text style={styles.important}>⭐ Important</Text>}
      </View>
    </View>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.colors.surface,
    borderRadius: theme.borderRadius.lg,
    padding: theme.spacing.md,
    marginHorizontal: theme.spacing.md,
    marginVertical: theme.spacing.xs,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: theme.spacing.sm,
  },
  typeContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing.xs,
  },
  icon: {
    fontSize: 18,
  },
  typeLabel: {
    fontSize: theme.fontSize.sm,
    color: theme.colors.primaryLight,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  deleteButton: {
    fontSize: 16,
    opacity: 0.6,
  },
  content: {
    fontSize: theme.fontSize.md,
    color: theme.colors.text,
    lineHeight: 22,
    marginBottom: theme.spacing.sm,
  },
  tagsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: theme.spacing.xs,
    marginBottom: theme.spacing.sm,
  },
  tag: {
    backgroundColor: theme.colors.card,
    paddingHorizontal: theme.spacing.sm,
    paddingVertical: 2,
    borderRadius: theme.borderRadius.pill,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  tagText: {
    fontSize: theme.fontSize.xs,
    color: theme.colors.textSecondary,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  date: {
    fontSize: theme.fontSize.xs,
    color: theme.colors.textMuted,
  },
  important: {
    fontSize: theme.fontSize.xs,
    color: theme.colors.secondary,
  },
});
