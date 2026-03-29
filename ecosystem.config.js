module.exports = {
  apps: [{
    name: 'nobi-bot',
    script: 'app/bot.py',
    interpreter: 'python3',
    cwd: '/root/project-nobi',
    max_memory_restart: '1024M',
    env: {
      CHUTES_API_KEY: process.env.CHUTES_API_KEY || '',
      HF_API_TOKEN: process.env.HF_API_TOKEN || '',
      HF_ASR_MODEL: process.env.HF_ASR_MODEL || 'openai/whisper-large-v3-turbo',
      OPENROUTER_API_KEY: process.env.OPENROUTER_API_KEY || ''
    }
  },

  // ── MemoryBear Cron Jobs ─────────────────────────────────────────────────

  {
    // Nightly self-reflection: detect & flag memory conflicts (2am daily)
    name: 'memorybear-reflection',
    script: 'scripts/memorybear_cron.py',
    interpreter: 'python3',
    cwd: '/root/project-nobi',
    cron_restart: '0 2 * * *',
    autorestart: false,
    watch: false,
    env: {
      CHUTES_API_KEY: process.env.CHUTES_API_KEY || '',
      MEMORYBEAR_TASK: 'reflection',
    }
  },

  {
    // Weekly implicit inference: infer habits/preferences (Sunday 3am)
    name: 'memorybear-inference',
    script: 'scripts/memorybear_cron.py',
    interpreter: 'python3',
    cwd: '/root/project-nobi',
    cron_restart: '0 3 * * 0',
    autorestart: false,
    watch: false,
    env: {
      CHUTES_API_KEY: process.env.CHUTES_API_KEY || '',
      MEMORYBEAR_TASK: 'inference',
    }
  },

  {
    // Weekly ACT-R forgetting pass (Saturday 4am)
    name: 'memorybear-forgetting',
    script: 'scripts/memorybear_cron.py',
    interpreter: 'python3',
    cwd: '/root/project-nobi',
    cron_restart: '0 4 * * 6',
    autorestart: false,
    watch: false,
    env: {
      CHUTES_API_KEY: process.env.CHUTES_API_KEY || '',
      MEMORYBEAR_TASK: 'forgetting',
    }
  }]
}
