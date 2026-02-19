import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.SearchResult;
import com.atlassian.jira.client.api.domain.User;
import com.atlassian.jira.client.api.domain.WorklogEntry;

import java.io.IOException;
import java.util.List;

public class JavaAgentJiraIntegration {

    public static void main(String[] args) {
        // Configuração do Jira Client
        String jiraUrl = "https://your-jira-instance.com";
        String username = "your-username";
        String password = "your-password";

        try (JiraClient client = new JiraClientBuilder(jiraUrl).username(username).password(password).build()) {

            // Função para criar um novo issue
            createIssue(client);

            // Função para buscar issues por título
            searchIssuesByTitle(client, "Java Agent");

            // Função para adicionar trabalhador a um issue
            addWorklogEntry(client, "issue-key-123", "John Doe", 8.0);

        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private static void createIssue(JiraClient client) throws IOException {
        Issue issue = new Issue()
                .setProjectKey("YOUR-PROJECT")
                .setSummary("Java Agent Integration")
                .setDescription("Tracking of Java Agent integration in Jira");

        client.createIssue(issue);
        System.out.println("Issue created successfully");
    }

    private static void searchIssuesByTitle(JiraClient client, String title) throws IOException {
        SearchResult result = client.searchJql(title);

        if (!result.isEmpty()) {
            for (Issue issue : result.getIssues()) {
                System.out.println("Found issue: " + issue.getKey());
            }
        } else {
            System.out.println("No issues found with the title: " + title);
        }
    }

    private static void addWorklogEntry(JiraClient client, String issueKey, String username, double hours) throws IOException {
        WorklogEntry worklogEntry = new WorklogEntry()
                .setIssueKey(issueKey)
                .setAuthor(username)
                .setDescription("Adding Java Agent integration")
                .setDuration(hours);

        client.addWorklog(worklogEntry);
        System.out.println("Worklog entry added successfully");
    }
}