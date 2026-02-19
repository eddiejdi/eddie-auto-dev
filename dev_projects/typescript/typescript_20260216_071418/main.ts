import { JiraClient } from 'jira-client';
import { Agent } from './agent';

class Scrum10 {
    private jiraClient: JiraClient;
    private agent: Agent;

    constructor(jiraHost: string, username: string, password: string) {
        this.jiraClient = new JiraClient({
            host: jiraHost,
            username: username,
            password: password
        });
        this.agent = new Agent();
    }

    async startScrum() {
        try {
            await this.jiraClient.login();
            console.log('Logged in to Jira');

            // Start the scrum process
            const sprintId = '12345'; // Replace with actual sprint ID
            const startDate = new Date(); // Replace with actual start date

            await this.agent.startScrum(sprintId, startDate);
            console.log('Scrum started successfully');

            // Monitor activities and manage tasks
            while (true) {
                const activity = await this.agent.getLatestActivity();
                console.log(`New activity: ${activity}`);

                if (activity === 'Task completed') {
                    await this.agent.completeTask(activity);
                    console.log('Task completed');
                }
            }
        } catch (error) {
            console.error('Error in Scrum10:', error);
        } finally {
            await this.jiraClient.logout();
            console.log('Logged out from Jira');
        }
    }

    async main() {
        const jiraHost = 'https://your-jira-host.com';
        const username = 'your-username';
        const password = 'your-password';

        const scrum10 = new Scrum10(jiraHost, username, password);
        await scrum10.startScrum();
    }
}

// Execute the main function
if (require.main === module) {
    Scrum10.main().catch(error => console.error('Error in main:', error));
}