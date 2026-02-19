import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.WorklogEntry;

import java.io.IOException;
import java.util.Date;

public class JavaAgentTest {

    @org.junit.jupiter.api.Test
    public void testRegisterNewIssue() throws IOException {
        // Configuração do JIRA
        String jiraUrl = "https://your-jira-instance.atlassian.net";
        String username = "your-username";
        String password = "your-password";

        // Criando o cliente JIRA
        JiraClient client = new JiraClientBuilder(jiraUrl).basicAuth(username, password).build();

        // Função para registrar um novo issue no JIRA
        Issue issue = new Issue();
        issue.setProjectKey("YOUR_PROJECT_KEY");
        issue.setSummary("Teste de issue no Java Agent");
        issue.setDescription("Este é um teste de issue criado pelo Java Agent");

        // Criando o issue no JIRA
        Issue createdIssue = client.createIssue(issue);

        // Verificando se o issue foi criado corretamente
        assert createdIssue != null : "Issue não criado";
        assert createdIssue.getId() != null : "ID do issue é nulo";
    }

    @org.junit.jupiter.api.Test
    public void testRegisterWorklogEntry() throws IOException {
        // Configuração do JIRA
        String jiraUrl = "https://your-jira-instance.atlassian.net";
        String username = "your-username";
        String password = "your-password";

        // Criando o cliente JIRA
        JiraClient client = new JiraClientBuilder(jiraUrl).basicAuth(username, password).build();

        // Função para registrar um novo issue no JIRA
        Issue issue = new Issue();
        issue.setProjectKey("YOUR_PROJECT_KEY");
        issue.setSummary("Teste de issue no Java Agent");
        issue.setDescription("Este é um teste de issue criado pelo Java Agent");

        // Criando o issue no JIRA
        Issue createdIssue = client.createIssue(issue);

        // Função para registrar um novo worklog entry no JIRA
        WorklogEntry worklogEntry = new WorklogEntry();
        worklogEntry.setIssueId(createdIssue.getId());
        worklogEntry.setTimeSpent("1h");
        worklogEntry.setDescription("Este é um teste de worklog entry criado pelo Java Agent");

        // Criando o worklog entry no JIRA
        client.createWorklog(worklogEntry);

        // Verificando se o worklog entry foi criado corretamente
        assert worklogEntry != null : "Worklog entry não criado";
        assert worklogEntry.getId() != null : "ID do worklog entry é nulo";
    }

    @org.junit.jupiter.api.Test
    public void testRegisterNewIssueWithInvalidProjectKey() throws IOException {
        // Configuração do JIRA
        String jiraUrl = "https://your-jira-instance.atlassian.net";
        String username = "your-username";
        String password = "your-password";

        // Criando o cliente JIRA
        JiraClient client = new JiraClientBuilder(jiraUrl).basicAuth(username, password).build();

        // Função para registrar um novo issue no JIRA com projeto inválido
        Issue issue = new Issue();
        issue.setProjectKey("INVALID_PROJECT_KEY");
        issue.setSummary("Teste de issue no Java Agent");
        issue.setDescription("Este é um teste de issue criado pelo Java Agent");

        try {
            // Criando o issue no JIRA
            client.createIssue(issue);
            assert false : "Deveria lançar uma exceção";
        } catch (IOException e) {
            System.out.println("Exceção capturada: " + e.getMessage());
        }
    }

    @org.junit.jupiter.api.Test
    public void testRegisterWorklogEntryWithInvalidTimeSpent() throws IOException {
        // Configuração do JIRA
        String jiraUrl = "https://your-jira-instance.atlassian.net";
        String username = "your-username";
        String password = "your-password";

        // Criando o cliente JIRA
        JiraClient client = new JiraClientBuilder(jiraUrl).basicAuth(username, password).build();

        // Função para registrar um novo issue no JIRA com projeto inválido
        Issue issue = new Issue();
        issue.setProjectKey("YOUR_PROJECT_KEY");
        issue.setSummary("Teste de issue no Java Agent");
        issue.setDescription("Este é um teste de issue criado pelo Java Agent");

        try {
            // Criando o issue no JIRA
            client.createIssue(issue);
            assert false : "Deveria lançar uma exceção";
        } catch (IOException e) {
            System.out.println("Exceção capturada: " + e.getMessage());
        }
    }

    @org.junit.jupiter.api.Test
    public void testRegisterWorklogEntryWithInvalidDescription() throws IOException {
        // Configuração do JIRA
        String jiraUrl = "https://your-jira-instance.atlassian.net";
        String username = "your-username";
        String password = "your-password";

        // Criando o cliente JIRA
        JiraClient client = new JiraClientBuilder(jiraUrl).basicAuth(username, password).build();

        // Função para registrar um novo issue no JIRA com projeto inválido
        Issue issue = new Issue();
        issue.setProjectKey("YOUR_PROJECT_KEY");
        issue.setSummary("Teste de issue no Java Agent");
        issue.setDescription("");

        try {
            // Criando o issue no JIRA
            client.createIssue(issue);
            assert false : "Deveria lançar uma exceção";
        } catch (IOException e) {
            System.out.println("Exceção capturada: " + e.getMessage());
        }
    }
}