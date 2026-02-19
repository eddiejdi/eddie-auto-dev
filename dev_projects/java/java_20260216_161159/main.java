import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;

import java.util.List;

public class JavaAgentJiraIntegration {

    public static void main(String[] args) {
        // Configuração do Jira
        String jiraUrl = "http://your-jira-url";
        String username = "your-username";
        String password = "your-password";

        try (Jira jira = new Jira(jiraUrl, username, password)) {
            JiraServiceContext serviceContext = new JiraServiceContext();
            IssueManager issueManager = jira.getIssueManager(serviceContext);
            ProjectManager projectManager = jira.getProjectManager(serviceContext);

            // Exemplo de uso: Criar um novo issue
            String issueKey = "NEW-001";
            String summary = "Teste de Jira Integration";
            String description = "Este é um teste para integrar o Java Agent com Jira.";

            Issue newIssue = issueManager.create(issueKey, summary, description);
            System.out.println("Issue criado: " + newIssue.getKey());

            // Exemplo de uso: Listar todas as issues
            List<Issue> issues = issueManager.getAllIssues();
            for (Issue issue : issues) {
                System.out.println("Issue: " + issue.getKey() + ", Summary: " + issue.getSummary());
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}