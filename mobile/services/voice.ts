/**
 * Voice service for Nori — Speech-to-Text and Text-to-Speech.
 * Uses expo-speech for TTS and server-side Whisper for STT.
 */

import * as Speech from 'expo-speech';
import { api } from './api';

// ─── Types ───────────────────────────────────────────────────────────────────

export interface VoiceConfig {
  /** TTS language code */
  language: string;
  /** TTS speech rate (0.5 – 2.0) */
  rate: number;
  /** TTS pitch (0.5 – 2.0) */
  pitch: number;
  /** Whether voice output is enabled */
  enabled: boolean;
}

export interface VoiceResult {
  transcription: string;
  responseText: string;
  responseAudio?: string; // Base64 encoded audio from server
}

// ─── Default Config ──────────────────────────────────────────────────────────

const DEFAULT_CONFIG: VoiceConfig = {
  language: 'en-US',
  rate: 0.95,
  pitch: 1.1, // Slightly higher pitch for warm, friendly Nori voice
  enabled: true,
};

// ─── Voice Service ───────────────────────────────────────────────────────────

class VoiceService {
  private config: VoiceConfig = { ...DEFAULT_CONFIG };
  private isSpeaking = false;
  private available = false;

  /**
   * Initialize voice service — check availability.
   */
  async init(): Promise<boolean> {
    try {
      // Check if TTS is available
      const voices = await Speech.getAvailableVoicesAsync();
      this.available = voices.length > 0;
      return this.available;
    } catch {
      this.available = false;
      return false;
    }
  }

  /**
   * Check if voice features are available.
   */
  isAvailable(): boolean {
    return this.available;
  }

  /**
   * Update voice configuration.
   */
  setConfig(config: Partial<VoiceConfig>): void {
    this.config = { ...this.config, ...config };
  }

  getConfig(): VoiceConfig {
    return { ...this.config };
  }

  // ─── Text-to-Speech ──────────────────────────────────────────────────

  /**
   * Speak text using device TTS (Nori's voice).
   */
  async speak(text: string): Promise<void> {
    if (!this.config.enabled || !this.available) return;

    // Stop any current speech
    if (this.isSpeaking) {
      await this.stopSpeaking();
    }

    return new Promise<void>((resolve, reject) => {
      this.isSpeaking = true;

      Speech.speak(text, {
        language: this.config.language,
        rate: this.config.rate,
        pitch: this.config.pitch,
        onDone: () => {
          this.isSpeaking = false;
          resolve();
        },
        onError: (err) => {
          this.isSpeaking = false;
          reject(err);
        },
        onStopped: () => {
          this.isSpeaking = false;
          resolve();
        },
      });
    });
  }

  /**
   * Stop current speech.
   */
  async stopSpeaking(): Promise<void> {
    if (this.isSpeaking) {
      Speech.stop();
      this.isSpeaking = false;
    }
  }

  /**
   * Check if currently speaking.
   */
  getIsSpeaking(): boolean {
    return this.isSpeaking;
  }

  // ─── Server-side Voice Processing ──────────────────────────────────────

  /**
   * Send audio to server for STT + get Nori's response + TTS.
   * Full voice pipeline: record → transcribe → respond → speak.
   */
  async processVoiceMessage(
    audioBase64: string,
    audioFormat = 'wav',
    language = 'en',
  ): Promise<VoiceResult | null> {
    try {
      const result = await api.sendVoice(audioBase64, audioFormat, language);

      if (!result.ok || !result.data) {
        return null;
      }

      const { transcription, responseText, responseAudio } = result.data;

      // Auto-speak the response if TTS is enabled
      if (this.config.enabled && responseText) {
        await this.speak(responseText);
      }

      return { transcription, responseText, responseAudio };
    } catch {
      return null;
    }
  }

  // ─── Available Voices ──────────────────────────────────────────────────

  /**
   * Get available TTS voices on this device.
   */
  async getVoices(): Promise<Speech.Voice[]> {
    try {
      return await Speech.getAvailableVoicesAsync();
    } catch {
      return [];
    }
  }
}

export const voiceService = new VoiceService();
