import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.CustomField;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.issue.fields.DateField;
import com.atlassian.jira.issue.fields.NumberField;
import com.atlassian.jira.issue.fields.UserPickerField;
import com.atlassian.jira.issue.fields.SelectField;
import com.atlassian.jira.issue.fields.MultipleSelectField;
import com.atlassian.jira.issue.fields.BooleanField;
import com.atlassian.jira.issue.fields.AttachmentField;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class JavaAgentTest {

    private Jira jira;
    private FieldManager fieldManager;
    private CustomFieldManager customFieldManager;

    @Before
    public void setUp() {
        // Configuração do Jira
        jira = new Jira(); // Implemente a configuração correta do Jira

        // Configuração dos campos personalizados
        fieldManager = new FieldManager(); // Implemente a configuração correta dos campos personalizados
        customFieldManager = new CustomFieldManager(); // Implemente a configuração correta dos campos personalizados

        JavaAgent javaAgent = new JavaAgent(jira, fieldManager, customFieldManager);
    }

    @Test
    public void testRegisterEvent() {
        try {
            Issue issue = jira.getIssue("ABC-123");
            if (issue == null) {
                throw new IllegalArgumentException("Issue not found: ABC-123");
            }
            CustomField eventField = customFieldManager.getCustomFieldByName("Event");
            if (eventField == null) {
                throw new IllegalArgumentException("Event field not found");
            }
            TextField textField = (TextField) eventField.getFieldObject();
            textField.setValue(issue, "Completed the task");

            assertEquals(textField.getValue(issue), "Completed the task", "The value of the Event field should be 'Completed the task'");
        } catch (Exception e) {
            System.err.println("Error registering event: " + e.getMessage());
        }
    }

    @Test
    public void testMonitorActivity() {
        try {
            Issue issue = jira.getIssue("ABC-123");
            if (issue == null) {
                throw new IllegalArgumentException("Issue not found: ABC-123");
            }
            CustomField activityField = customFieldManager.getCustomFieldByName("Activity");
            if (activityField == null) {
                throw new IllegalArgumentException("Activity field not found");
            }
            TextField textField = (TextField) activityField.getFieldObject();
            textField.setValue(issue, "John Doe logged in");

            assertEquals(textField.getValue(issue), "John Doe logged in", "The value of the Activity field should be 'John Doe logged in'");
        } catch (Exception e) {
            System.err.println("Error monitoring activity: " + e.getMessage());
        }
    }

    @Test
    public void testRegisterPerformance() {
        try {
            Issue issue = jira.getIssue("ABC-123");
            if (issue == null) {
                throw new IllegalArgumentException("Issue not found: ABC-123");
            }
            CustomField performanceField = customFieldManager.getCustomFieldByName("Performance");
            if (performanceField == null) {
                throw new IllegalArgumentException("Performance field not found");
            }
            TextField textField = (TextField) performanceField.getFieldObject();
            textField.setValue(issue, "High CPU Usage Detected");

            assertEquals(textField.getValue(issue), "High CPU Usage Detected", "The value of the Performance field should be 'High CPU Usage Detected'");
        } catch (Exception e) {
            System.err.println("Error registering performance: " + e.getMessage());
        }
    }

    @After
    public void tearDown() {
        // Limpeza após os testes
    }
}