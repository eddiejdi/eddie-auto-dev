const axios = require('axios');
const { exec } = require('child_process');

describe('JavaScriptAgent', () => {
  let agent;

  beforeEach(() => {
    agent = new JavaScriptAgent('https://your-jira-instance.atlassian.net', 'your-api-token');
  });

  describe('#trackActivity', () => {
    it('should track an activity successfully with valid data', async () => {
      const response = await agent.trackActivity({
        title: 'Implement JavaScript Agent with Jira',
        description: 'This is a test to track activities in Jira using the JavaScript Agent.'
      });

      expect(response.data).toHaveProperty('summary');
      expect(response.data).toHaveProperty('description');
    });

    it('should throw an error if the summary is empty', async () => {
      await expect(agent.trackActivity({
        title: '',
        description: 'This is a test to track activities in Jira using the JavaScript Agent.'
      })).rejects.toThrowError('Summary cannot be empty');
    });
  });

  describe('#executeCommand', () => {
    it('should execute a command successfully with valid data', async () => {
      const { stdout, stderr } = await exec('node your-script.js');

      expect(stdout).toContain('Your script executed successfully');
    });

    it('should throw an error if the command fails', async () => {
      await expect(exec('nonexistent-command')).rejects.toThrowError('Command failed with exit code 127');
    });
  });
});