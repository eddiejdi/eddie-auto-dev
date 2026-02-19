import { Scrum10 } from './scrum10';
import { Agent } from './agent';

describe('Scrum10', () => {
    let scrum10: Scrum10;
    let agent: Agent;

    beforeEach(() => {
        scrum10 = new Scrum10('https://your-jira-host.com', 'your-username', 'your-password');
        agent = new Agent();
    });

    afterEach(() => {
        // Cleanup code if needed
    });

    describe('startScrum', () => {
        it('should log in to Jira and start the scrum process', async () => {
            const spyLogin = jest.spyOn(scrum10.jiraClient, 'login');
            const spyStartScrum = jest.spyOn(agent, 'startScrum');

            await scrum10.startScrum();

            expect(spyLogin).toHaveBeenCalledWith();
            expect(spyStartScrum).toHaveBeenCalledWith('12345', new Date());
        });

        it('should handle errors during login', async () => {
            const spyLogin = jest.spyOn(scrum10.jiraClient, 'login').mockRejectedValue(new Error('Invalid credentials'));

            await scrum10.startScrum();

            expect(console.error).toHaveBeenCalledWith('Error in Scrum10: Invalid credentials');
        });

        it('should handle errors during scrum start', async () => {
            const spyStartScrum = jest.spyOn(agent, 'startScrum').mockRejectedValue(new Error('Failed to start scrum'));

            await scrum10.startScrum();

            expect(console.error).toHaveBeenCalledWith('Error in Scrum10: Failed to start scrum');
        });
    });

    describe('main', () => {
        it('should log in to Jira and start the scrum process', async () => {
            const spyLogin = jest.spyOn(scrum10.jiraClient, 'login');
            const spyStartScrum = jest.spyOn(agent, 'startScrum');

            await scrum10.main();

            expect(spyLogin).toHaveBeenCalledWith();
            expect(spyStartScrum).toHaveBeenCalledWith('12345', new Date());
        });

        it('should handle errors during login', async () => {
            const spyLogin = jest.spyOn(scrum10.jiraClient, 'login').mockRejectedValue(new Error('Invalid credentials'));

            await scrum10.main();

            expect(console.error).toHaveBeenCalledWith('Error in Scrum10: Invalid credentials');
        });

        it('should handle errors during scrum start', async () => {
            const spyStartScrum = jest.spyOn(agent, 'startScrum').mockRejectedValue(new Error('Failed to start scrum'));

            await scrum10.main();

            expect(console.error).toHaveBeenCalledWith('Error in Scrum10: Failed to start scrum');
        });
    });

    describe('Agent', () => {
        it('should handle errors during activity retrieval', async () => {
            const spyGetLatestActivity = jest.spyOn(agent, 'getLatestActivity').mockRejectedValue(new Error('Failed to get latest activity'));

            await agent.getLatestActivity();

            expect(console.error).toHaveBeenCalledWith('Error in Agent: Failed to get latest activity');
        });

        it('should handle errors during task completion', async () => {
            const spyCompleteTask = jest.spyOn(agent, 'completeTask').mockRejectedValue(new Error('Failed to complete task'));

            await agent.completeTask('Task completed');

            expect(console.error).toHaveBeenCalledWith('Error in Agent: Failed to complete task');
        });
    });
});