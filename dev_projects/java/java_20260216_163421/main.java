import com.atlassian.jira.ComponentManager;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;

public class JavaAgentJiraIntegration {

    public static void main(String[] args) {
        // Inicializa o JIRA ComponentManager
        ComponentManager componentManager = ComponentManager.getInstance();

        // Obtém a IssueManager e ProjectManager
        IssueManager issueManager = componentManager.getComponent(IssueManager.class);
        ProjectManager projectManager = componentManager.getComponent(ProjectManager.class);

        // Exemplo de uso: Obter uma Issue por ID
        long issueId = 12345L;
        try {
            Issue issue = issueManager.getIssue(issueId);
            System.out.println("Issue found: " + issue.getKey());
        } catch (Exception e) {
            System.err.println("Error retrieving issue: " + e.getMessage());
        }

        // Exemplo de uso: Obter todas as Issues do Projeto
        try {
            Project project = projectManager.getProjectByKey("PROJECT_KEY");
            for (Issue issue : project.getIssues()) {
                System.out.println("Issue found in project: " + issue.getKey());
            }
        } catch (Exception e) {
            System.err.println("Error retrieving issues from project: " + e.getMessage());
        }

        // Exemplo de uso: Criar uma nova Issue
        try {
            Project project = projectManager.getProjectByKey("PROJECT_KEY");
            Issue newIssue = issueManager.createIssue(project, "New Test Issue", "This is a test issue.");
            System.out.println("New issue created: " + newIssue.getKey());
        } catch (Exception e) {
            System.err.println("Error creating issue: " + e.getMessage());
        }
    }
}