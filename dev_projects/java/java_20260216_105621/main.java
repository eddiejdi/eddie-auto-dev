import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.WorklogEntry;

import java.io.IOException;
import java.util.Date;

public class JavaAgent {

    public static void main(String[] args) {
        try {
            // Configuração do JIRA
            String jiraUrl = "https://your-jira-instance.atlassian.net";
            String username = "your-username";
            String password = "your-password";

            // Criando o cliente JIRA
            JiraClient client = new JiraClientBuilder(jiraUrl).basicAuth(username, password).build();

            // Função para registrar um novo issue no JIRA
            registerNewIssue(client);

            // Função para registrar um novo worklog entry no JIRA
            registerWorklogEntry(client);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private static void registerNewIssue(JiraClient client) throws IOException {
        Issue issue = new Issue();
        issue.setProjectKey("YOUR_PROJECT_KEY");
        issue.setSummary("Teste de issue no Java Agent");
        issue.setDescription("Este é um teste de issue criado pelo Java Agent");

        // Criando o issue no JIRA
        Issue createdIssue = client.createIssue(issue);

        System.out.println("Issue criado com ID: " + createdIssue.getId());
    }

    private static void registerWorklogEntry(JiraClient client) throws IOException {
        WorklogEntry worklogEntry = new WorklogEntry();
        worklogEntry.setIssueId(createdIssue.getId());
        worklogEntry.setTimeSpent("1h");
        worklogEntry.setDescription("Este é um teste de worklog entry criado pelo Java Agent");

        // Criando o worklog entry no JIRA
        client.createWorklog(worklogEntry);

        System.out.println("Worklog entry criado com ID: " + worklogEntry.getId());
    }
}