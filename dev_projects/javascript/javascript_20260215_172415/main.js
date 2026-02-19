const { exec } = require('child_process');

class JavaScriptAgent {
  constructor(options) {
    this.options = options;
  }

  async start() {
    try {
      const command = `java -jar ${this.options.agentPath} --url ${this.options.jiraUrl}`;
      await exec(command);
      console.log('JavaScript Agent started successfully');
    } catch (error) {
      console.error('Error starting JavaScript Agent:', error);
    }
  }

  async stop() {
    try {
      const command = `java -jar ${this.options.agentPath} --stop`;
      await exec(command);
      console.log('JavaScript Agent stopped successfully');
    } catch (error) {
      console.error('Error stopping JavaScript Agent:', error);
    }
  }
}

module.exports = JavaScriptAgent;