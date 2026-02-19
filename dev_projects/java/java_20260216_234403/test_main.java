import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraException;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;

public class JavaAgentJiraIntegrationTest {

    private static final String JIRA_URL = "http://your-jira-url";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    @Before
    public void setUp() throws Exception {
        // Configuração do Jira
        try (Jira jira = new Jira(JIRA_URL, USERNAME, PASSWORD)) {

            // Obter o Projeto
            Project project = jira.getProject("YOUR_PROJECT_KEY");

            // Obter o CustomFieldManager
            FieldManager fieldManager = jira.getFieldManager();

            // Criar um novo campo customizado para tracking de atividades
            CustomFieldManager customFieldManager = jira.getCustomFieldManager();
            String customFieldName = "Tracking Activity";
            com.atlassian.jira.issue.customfields.CustomFieldType customFieldType = customFieldManager.getCustomFieldTypeByName("Text");
            if (customFieldType != null) {
                com.atlassian.jira.issue.fields.CustomField customField = fieldManager.createCustomField(customFieldName, customFieldType);
            }

            // Criar uma nova Issue
            String issueKey = "YOUR_ISSUE_KEY";
            Issue issue = jira.getIssue(issueKey);

            // Adicionar um novo campo customizado à Issue
            TextField trackingActivityField = (TextField) customFieldManager.getFieldByName("Tracking Activity");
            if (trackingActivityField != null) {
                issue.addCustomFieldValue(trackingActivityField, "In progress");
            }

        } catch (JiraException e) {
            e.printStackTrace();
        }
    }

    @Test
    public void testCreateIssueWithValidValues() throws Exception {
        // Teste de criação de Issue com valores válidos
        String issueKey = "NEW-123";
        Issue newIssue = jira.createIssue(issueKey, "Summary", "Description");
        assertNotNull(newIssue);
        assertEquals("NEW-123", newIssue.getKey());
    }

    @Test(expected = JiraException.class)
    public void testCreateIssueWithInvalidValues() throws Exception {
        // Teste de criação de Issue com valores inválidos
        String issueKey = "INVALID-!@#";
        jira.createIssue(issueKey, "Summary", "Description");
    }

    @After
    public void tearDown() throws Exception {
        // Limpeza após os testes
        try (Jira jira = new Jira(JIRA_URL, USERNAME, PASSWORD)) {

            // Obter o Projeto
            Project project = jira.getProject("YOUR_PROJECT_KEY");

            // Obter o CustomFieldManager
            FieldManager fieldManager = jira.getFieldManager();

            // Criar um novo campo customizado para tracking de atividades
            CustomFieldManager customFieldManager = jira.getCustomFieldManager();
            String customFieldName = "Tracking Activity";
            com.atlassian.jira.issue.customfields.CustomFieldType customFieldType = customFieldManager.getCustomFieldTypeByName("Text");
            if (customFieldType != null) {
                com.atlassian.jira.issue.fields.CustomField customField = fieldManager.createCustomField(customFieldName, customFieldType);
            }

            // Criar uma nova Issue
            String issueKey = "YOUR_ISSUE_KEY";
            Issue issue = jira.getIssue(issueKey);

            // Adicionar um novo campo customizado à Issue
            TextField trackingActivityField = (TextField) customFieldManager.getFieldByName("Tracking Activity");
            if (trackingActivityField != null) {
                issue.addCustomFieldValue(trackingActivityField, "In progress");
            }

        } catch (JiraException e) {
            e.printStackTrace();
        }
    }
}