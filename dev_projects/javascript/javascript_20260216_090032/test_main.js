const agent = require('js-agent-sdk');

describe('startMonitoring', () => {
  it('should start monitoring with valid credentials', async () => {
    // Mock the agent.config method to return a Promise that resolves immediately
    jest.spyOn(agent, 'config').mockResolvedValue({});

    // Mock the agent.on method to resolve immediately
    jest.spyOn(agent, 'on').mockResolvedValue();

    // Call the startMonitoring function
    await startMonitoring();

    // Verify that the on method was called with the correct event name
    expect(agent.on).toHaveBeenCalledWith('activity');
  });

  it('should throw an error if credentials are invalid', async () => {
    // Mock the agent.config method to return a Promise that rejects immediately with an error
    jest.spyOn(agent, 'config').mockRejectedValue(new Error('Invalid credentials'));

    // Call the startMonitoring function and expect an error
    await expect(startMonitoring()).rejects.toThrowError('Invalid credentials');
  });
});

describe('startMonitoring', () => {
  it('should send activity to Jira with valid event', async () => {
    // Mock the agent.send method to resolve immediately
    jest.spyOn(agent, 'send').mockResolvedValue();

    // Call the startMonitoring function and expect the send method to be called with the correct event name
    await startMonitoring();

    expect(agent.send).toHaveBeenCalledWith({ name: 'Test Activity' });
  });

  it('should throw an error if sending activity fails', async () => {
    // Mock the agent.send method to return a Promise that rejects immediately with an error
    jest.spyOn(agent, 'send').mockRejectedValue(new Error('Failed to send activity'));

    // Call the startMonitoring function and expect an error
    await expect(startMonitoring()).rejects.toThrowError('Failed to send activity');
  });
});