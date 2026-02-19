import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraFactory;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.issue.Issue;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class JavaAgent {

    private static final Logger logger = LoggerFactory.getLogger(JavaAgent.class);

    public static void main(String[] args) {
        try {
            // Configuração do Jira
            JiraFactory jiraFactory = new JiraFactory();
            Jira jira = jiraFactory.getJira();

            // Criação de um projeto (se necessário)
            Project project = jira.getProjectManager().createProject("MyProject", "My Project");

            // Criação de uma issue (se necessário)
            Issue issue = jira.createIssue(project, "Test Issue", "This is a test issue.");

            // Log de atividade
            logger.info("Activity logged: {}", issue.getKey());

        } catch (Exception e) {
            logger.error("Error integrating with Jira", e);
        }
    }
}