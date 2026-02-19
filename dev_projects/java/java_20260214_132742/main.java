import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.ProjectField;
import com.atlassian.jira.issue.fields.UserField;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.user.ApplicationUser;
import com.atlassian.jira.user.UserManager;

public class JavaAgentJiraIntegration {

    public static void main(String[] args) {
        // Configuração do Jira
        Jira jira = new Jira();
        JiraServiceContext serviceContext = new JiraServiceContext();

        // Configuração de campos e usuários
        FieldManager fieldManager = jira.getFieldManager();
        CustomFieldManager customFieldManager = jira.getCustomFieldManager();
        ProjectField projectField = fieldManager.getProjectFieldByName("Project");
        UserField userField = fieldManager.getUserFieldByName("User");

        // Configuração de usuário logado
        UserManager userManager = jira.getUserManager();
        ApplicationUser loggedInUser = userManager.getUserByName("user123");

        // Cria um novo projeto
        Project project = new Project();
        project.setName("MyProject");
        project.setDescription("This is my project description.");
        project.setKey("MP");
        project.setLead(loggedInUser);
        project.setProjectType(projectField.getProjectType());
        project.setAssignee(loggedInUser);

        // Cria um novo issue
        Issue issue = new Issue();
        issue.setProject(project);
        issue.setDescription("This is my issue description.");
        issue.setStatus(fieldManager.getStatusByName("Open"));
        issue.setReporter(loggedInUser);
        issue.setAssignee(loggedInUser);

        // Salva o projeto e o issue no Jira
        jira.createIssue(issue, serviceContext);
    }
}