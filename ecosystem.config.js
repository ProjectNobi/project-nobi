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
      HF_ASR_MODEL: process.env.HF_ASR_MODEL || 'openai/whisper-large-v3',
      OPENROUTER_API_KEY: process.env.OPENROUTER_API_KEY || ''
    }
  }]
}
