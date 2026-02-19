import { JiraClient } from 'jira-client';

class JiraIntegration {
    private jiraClient: JiraClient;

    constructor(jiraUrl: string, username: string, password: string) {
        this.jiraClient = new JiraClient({
            url: jiraUrl,
            auth: {
                username,
                password
            }
        });
    }

    async logActivity(activity: string): Promise<void> {
        try {
            await this.jiraClient.addCommentToIssue('YOUR_ISSUE_KEY', activity);
            console.log(`Logged activity: ${activity}`);
        } catch (error) {
            console.error(`Error logging activity: ${error.message}`);
        }
    }

    async monitorActivity(): Promise<void> {
        try {
            const issues = await this.jiraClient.searchIssues({
                jql: 'status = "In Progress"'
            });
            for (const issue of issues.issues) {
                console.log(`Monitoring issue: ${issue.key}`);
                // Add logic to check and log activity
            }
        } catch (error) {
            console.error(`Error monitoring activities: ${error.message}`);
        }
    }

    async registerLogs(): Promise<void> {
        try {
            const logs = await this.jiraClient.searchIssues({
                jql: 'status = "Completed"'
            });
            for (const issue of logs.issues) {
                console.log(`Registering log for issue: ${issue.key}`);
                // Add logic to register logs
            }
        } catch (error) {
            console.error(`Error registering logs: ${error.message}`);
        }
    }

    async main(): Promise<void> {
        const jiraUrl = 'https://your-jira-instance.atlassian.net';
        const username = 'YOUR_USERNAME';
        const password = 'YOUR_PASSWORD';

        const integration = new JiraIntegration(jiraUrl, username, password);

        await integration.logActivity('Starting development');
        await integration.monitorActivity();
        await integration.registerLogs();
    }
}

if (require.main === module) {
    new JiraIntegration().main();
}