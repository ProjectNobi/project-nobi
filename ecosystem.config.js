module.exports = {
  apps: [{
    name: 'nobi-bot',
    script: 'app/bot.py',
    interpreter: 'python3',
    cwd: '/root/project-nobi',
    max_memory_restart: '1024M',
    env: {
      CHUTES_API_KEY: process.env.CHUTES_API_KEY || ''
    }
  }]
}
