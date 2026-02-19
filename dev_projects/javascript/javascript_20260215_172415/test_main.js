const { exec } = require('child_process');
const JavaScriptAgent = require('./JavaScriptAgent');

describe('JavaScriptAgent', () => {
  let agent;

  beforeEach(() => {
    agent = new JavaScriptAgent({
      agentPath: 'path/to/agent.jar',
      jiraUrl: 'http://example.com'
    });
  });

  describe('#start()', () => {
    it('should start the JavaScript Agent successfully with valid options', async () => {
      await agent.start();
      expect(console.log).toHaveBeenCalledWith('JavaScript Agent started successfully');
    });

    it('should handle errors starting the JavaScript Agent', async () => {
      jest.spyOn(agent, 'exec').mockImplementationOnce(() => Promise.reject(new Error('Test error')));
      try {
        await agent.start();
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        expect(console.error).toHaveBeenCalledWith('Error starting JavaScript Agent:', error);
      }
    });
  });

  describe('#stop()', () => {
    it('should stop the JavaScript Agent successfully with valid options', async () => {
      await agent.stop();
      expect(console.log).toHaveBeenCalledWith('JavaScript Agent stopped successfully');
    });

    it('should handle errors stopping the JavaScript Agent', async () => {
      jest.spyOn(agent, 'exec').mockImplementationOnce(() => Promise.reject(new Error('Test error')));
      try {
        await agent.stop();
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
        expect(console.error).toHaveBeenCalledWith('Error stopping JavaScript Agent:', error);
      }
    });
  });
});