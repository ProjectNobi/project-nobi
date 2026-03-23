/**
 * Memories screen — view, search, filter, and manage Nori's memories.
 */

import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  TextInput,
  StyleSheet,
  Pressable,
  Alert,
  ActivityIndicator,
  Share,
} from 'react-native';
import { theme } from '../../styles/theme';
import { useMemory } from '../../hooks/useMemory';
import { MemoryCard } from '../../components/MemoryCard';
import type { Memory } from '../../services/api';

// ─── Filter Types ────────────────────────────────────────────────────────────

const FILTER_OPTIONS: Array<{ key: Memory['type'] | 'all'; label: string; icon: string }> = [
  { key: 'all', label: 'All', icon: '🔍' },
  { key: 'fact', label: 'Facts', icon: '📌' },
  { key: 'preference', label: 'Likes', icon: '❤️' },
  { key: 'event', label: 'Events', icon: '📅' },
  { key: 'context', label: 'Context', icon: '💭' },
  { key: 'emotion', label: 'Feelings', icon: '😊' },
];

// ─── Screen ──────────────────────────────────────────────────────────────────

export default function MemoriesScreen() {
  const {
    memories,
    allMemories,
    isLoading,
    error,
    searchQuery,
    filterType,
    fetchMemories,
    deleteMemory,
    exportMemories,
    deleteAllMemories,
    search,
    setFilter,
  } = useMemory();

  const [showSearch, setShowSearch] = useState(false);

  // ─── Export ──────────────────────────────────────────────────────────────

  const handleExport = useCallback(async () => {
    const json = await exportMemories();
    if (json) {
      try {
        await Share.share({
          message: json,
          title: 'Nori Memories Export',
        });
      } catch {
        Alert.alert('Export', 'Memories copied to clipboard');
      }
    }
  }, [exportMemories]);

  // ─── Delete all ──────────────────────────────────────────────────────────

  const handleDeleteAll = useCallback(() => {
    Alert.alert(
      '🗑️ Delete All Memories',
      'This will permanently delete all of Nori\'s memories about you. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete Everything',
          style: 'destructive',
          onPress: deleteAllMemories,
        },
      ],
    );
  }, [deleteAllMemories]);

  // ─── Render ──────────────────────────────────────────────────────────────

  const renderItem = useCallback(
    ({ item }: { item: Memory }) => <MemoryCard memory={item} onDelete={deleteMemory} />,
    [deleteMemory],
  );

  const keyExtractor = useCallback((item: Memory) => item.id, []);

  const EmptyState = () => (
    <View style={styles.emptyContainer}>
      <Text style={styles.emptyIcon}>🧠</Text>
      <Text style={styles.emptyTitle}>No memories yet</Text>
      <Text style={styles.emptySubtitle}>
        As you chat with Nori, she&apos;ll remember important things about you.
      </Text>
    </View>
  );

  return (
    <View style={styles.container}>
      {/* Stats bar */}
      <View style={styles.statsBar}>
        <Text style={styles.statsText}>{allMemories.length} memories</Text>
        <View style={styles.statsActions}>
          <Pressable onPress={() => setShowSearch(!showSearch)}>
            <Text style={styles.actionIcon}>🔍</Text>
          </Pressable>
          <Pressable onPress={handleExport}>
            <Text style={styles.actionIcon}>📤</Text>
          </Pressable>
          <Pressable onPress={handleDeleteAll}>
            <Text style={styles.actionIcon}>🗑️</Text>
          </Pressable>
        </View>
      </View>

      {/* Search bar */}
      {showSearch && (
        <TextInput
          style={styles.searchInput}
          value={searchQuery}
          onChangeText={search}
          placeholder="Search memories..."
          placeholderTextColor={theme.colors.textMuted}
          autoFocus
        />
      )}

      {/* Filter chips */}
      <View style={styles.filterRow}>
        {FILTER_OPTIONS.map((opt) => (
          <Pressable
            key={opt.key}
            style={[styles.filterChip, filterType === opt.key && styles.filterChipActive]}
            onPress={() => setFilter(opt.key)}
          >
            <Text style={styles.filterIcon}>{opt.icon}</Text>
            <Text
              style={[
                styles.filterLabel,
                filterType === opt.key && styles.filterLabelActive,
              ]}
            >
              {opt.label}
            </Text>
          </Pressable>
        ))}
      </View>

      {/* Error */}
      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>⚠️ {error}</Text>
        </View>
      )}

      {/* Memory list */}
      {isLoading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
        </View>
      ) : (
        <FlatList
          data={memories}
          renderItem={renderItem}
          keyExtractor={keyExtractor}
          ListEmptyComponent={EmptyState}
          contentContainerStyle={styles.listContent}
          onRefresh={fetchMemories}
          refreshing={isLoading}
          showsVerticalScrollIndicator={false}
        />
      )}
    </View>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  statsBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
  },
  statsText: {
    color: theme.colors.textSecondary,
    fontSize: theme.fontSize.sm,
  },
  statsActions: {
    flexDirection: 'row',
    gap: theme.spacing.md,
  },
  actionIcon: {
    fontSize: 20,
  },
  searchInput: {
    marginHorizontal: theme.spacing.md,
    marginTop: theme.spacing.sm,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    backgroundColor: theme.colors.surface,
    borderRadius: theme.borderRadius.md,
    color: theme.colors.text,
    fontSize: theme.fontSize.md,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
    gap: theme.spacing.sm,
    flexWrap: 'wrap',
  },
  filterChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: theme.spacing.sm + 2,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.borderRadius.pill,
    backgroundColor: theme.colors.surface,
    borderWidth: 1,
    borderColor: theme.colors.border,
    gap: 4,
  },
  filterChipActive: {
    backgroundColor: theme.colors.primary,
    borderColor: theme.colors.primary,
  },
  filterIcon: {
    fontSize: 14,
  },
  filterLabel: {
    fontSize: theme.fontSize.xs,
    color: theme.colors.textSecondary,
  },
  filterLabelActive: {
    color: theme.colors.text,
    fontWeight: '600',
  },
  errorBanner: {
    backgroundColor: 'rgba(255,107,107,0.1)',
    padding: theme.spacing.sm,
    marginHorizontal: theme.spacing.md,
    borderRadius: theme.borderRadius.sm,
    borderWidth: 1,
    borderColor: theme.colors.error,
  },
  errorText: {
    color: theme.colors.error,
    fontSize: theme.fontSize.sm,
    textAlign: 'center',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  listContent: {
    paddingVertical: theme.spacing.sm,
    flexGrow: 1,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: theme.spacing.xl,
    paddingTop: 100,
  },
  emptyIcon: {
    fontSize: 48,
  },
  emptyTitle: {
    fontSize: theme.fontSize.lg,
    fontWeight: '700',
    color: theme.colors.text,
    marginTop: theme.spacing.md,
  },
  emptySubtitle: {
    fontSize: theme.fontSize.md,
    color: theme.colors.textSecondary,
    textAlign: 'center',
    marginTop: theme.spacing.sm,
    lineHeight: 22,
  },
});
