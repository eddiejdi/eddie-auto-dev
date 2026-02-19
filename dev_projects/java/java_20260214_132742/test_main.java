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

public class JavaAgentJiraIntegrationTest {

    private Jira jira;
    private JiraServiceContext serviceContext;
    private FieldManager fieldManager;
    private CustomFieldManager customFieldManager;
    private ProjectField projectField;
    private UserField userField;
    private ApplicationUser loggedInUser;

    @Before
    public void setUp() {
        // Configuração do Jira
        jira = new Jira();
        serviceContext = new JiraServiceContext();

        // Configuração de campos e usuários
        fieldManager = jira.getFieldManager();
        customFieldManager = jira.getCustomFieldManager();
        projectField = fieldManager.getProjectFieldByName("Project");
        userField = fieldManager.getUserFieldByName("User");

        // Configuração de usuário logado
        userManager = jira.getUserManager();
        loggedInUser = userManager.getUserByName("user123");
    }

    @Test
    public void testCreateIssueWithValidData() {
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

    @Test(expected = IllegalArgumentException.class)
    public void testCreateIssueWithInvalidData() {
        // Cria um novo projeto com nome vazio
        Project project = new Project();
        project.setName("");
        project.setDescription("This is my project description.");
        project.setKey("MP");
        project.setLead(loggedInUser);
        project.setProjectType(projectField.getProjectType());
        project.setAssignee(loggedInUser);

        // Cria um novo issue com descrição vazia
        Issue issue = new Issue();
        issue.setProject(project);
        issue.setDescription("");
        issue.setStatus(fieldManager.getStatusByName("Open"));
        issue.setReporter(loggedInUser);
        issue.setAssignee(loggedInUser);

        // Salva o projeto e o issue no Jira
        jira.createIssue(issue, serviceContext);
    }
}