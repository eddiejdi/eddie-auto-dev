import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraException;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import org.apache.log4j.Logger;

public class JavaAgentTest {

    private static final Logger logger = Logger.getLogger(JavaAgentTest.class);

    @org.junit.Test
    public void testCreateProject() throws JiraException {
        // Configuração do JIRA
        Jira jira = new Jira("https://your-jira-url.com");
        ProjectManager projectManager = jira.getProjectManager();
        FieldManager fieldManager = jira.getFieldManager();

        // Cria um novo projeto
        Project project = projectManager.createProject("JavaAgent", "Java Agent Project");

        // Verifica se o projeto foi criado com sucesso
        assert project != null : "Failed to create project";
    }

    @org.junit.Test
    public void testCreateIssue() throws JiraException {
        // Configuração do JIRA
        Jira jira = new Jira("https://your-jira-url.com");
        ProjectManager projectManager = jira.getProjectManager();
        FieldManager fieldManager = jira.getFieldManager();

        // Cria um novo projeto
        Project project = projectManager.createProject("JavaAgent", "Java Agent Project");

        // Adiciona um campo personalizado para registro de logs
        CustomFieldManager customFieldManager = jira.getCustomFieldManager();
        TextField logField = customFieldManager.createTextField("log", "Log Field");
        fieldManager.updateIssue(project, null, logField);

        // Cria uma nova tarefa
        Issue issue = project.createIssue("JavaAgentTask", "Java Agent Task");

        // Verifica se a tarefa foi criada com sucesso
        assert issue != null : "Failed to create issue";
    }

    @org.junit.Test
    public void testUpdateLogField() throws JiraException {
        // Configuração do JIRA
        Jira jira = new Jira("https://your-jira-url.com");
        ProjectManager projectManager = jira.getProjectManager();
        FieldManager fieldManager = jira.getFieldManager();

        // Cria um novo projeto
        Project project = projectManager.createProject("JavaAgent", "Java Agent Project");

        // Adiciona um campo personalizado para registro de logs
        CustomFieldManager customFieldManager = jira.getCustomFieldManager();
        TextField logField = customFieldManager.createTextField("log", "Log Field");
        fieldManager.updateIssue(project, null, logField);

        // Cria uma nova tarefa
        Issue issue = project.createIssue("JavaAgentTask", "Java Agent Task");

        // Registra um log na tarefa
        logger.info("Executing JavaAgent task");

        // Atualiza o campo de registro de logs
        fieldManager.updateIssue(project, issue, logField);

        // Verifica se o log foi atualizado com sucesso
        assert logField.getValue(issue) != null : "Failed to update log field";
    }

    @org.junit.Test(expected = JiraException.class)
    public void testCreateProjectWithInvalidName() throws JiraException {
        // Configuração do JIRA
        Jira jira = new Jira("https://your-jira-url.com");
        ProjectManager projectManager = jira.getProjectManager();
        FieldManager fieldManager = jira.getFieldManager();

        // Tenta criar um projeto com nome inválido
        projectManager.createProject("JavaAgent", "Invalid Name Project");
    }
}