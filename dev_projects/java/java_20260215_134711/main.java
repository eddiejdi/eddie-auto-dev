import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraException;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import org.apache.log4j.Logger;

public class JavaAgent {

    private static final Logger logger = Logger.getLogger(JavaAgent.class);

    public static void main(String[] args) {
        try {
            // Configuração do JIRA
            Jira jira = new Jira("https://your-jira-url.com");
            ProjectManager projectManager = jira.getProjectManager();
            FieldManager fieldManager = jira.getFieldManager();

            // Cria um novo projeto
            Project project = projectManager.createProject("JavaAgent", "Java Agent Project");

            // Adiciona um campo personalizado para registro de logs
            CustomFieldManager customFieldManager = jira.getCustomFieldManager();
            TextField logField = customFieldManager.createTextField("log", "Log Field");
            fieldManager.updateIssue(project, issue, logField);

            // Cria uma nova tarefa
            Issue issue = project.createIssue("JavaAgentTask", "Java Agent Task");

            // Registra um log na tarefa
            logger.info("Executing JavaAgent task");

            // Atualiza o campo de registro de logs
            fieldManager.updateIssue(project, issue, logField);

        } catch (JiraException e) {
            logger.error("Error integrating with JIRA", e);
        }
    }
}