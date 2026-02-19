import com.atlassian.jira.ComponentManager;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomField;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.user.User;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class JavaAgentTest {

    private ComponentManager componentManager;
    private FieldManager fieldManager;
    private Issue issue;

    @BeforeEach
    public void setUp() {
        componentManager = ComponentManager.getInstance();
        fieldManager = componentManager.getFieldManager();

        // Criação de um novo issue
        issue = fieldManager.createIssue("My New Issue", "This is a test issue");

        // Adição de campos personalizados ao issue
        CustomField customField1 = fieldManager.getCustomFieldObjectByName("Custom Field 1");
        TextField textField1 = (TextField) customField1.getField();
        textField1.setValue(issue, "Value for Custom Field 1");

        CustomField customField2 = fieldManager.getCustomFieldObjectByName("Custom Field 2");
        TextField textField2 = (TextField) customField2.getField();
        textField2.setValue(issue, "Value for Custom Field 2");

        // Adição de um usuário ao issue
        User user = componentManager.getUserManager().getUserByKey("username");
        issue.addWatcher(user);
    }

    @Test
    public void testCreateIssue() {
        assertNotNull(issue);
        assertEquals("My New Issue", issue.getKey());
        assertEquals("This is a test issue", issue.getDescription());
    }

    @Test
    public void testAddCustomField1() {
        CustomField customField1 = fieldManager.getCustomFieldObjectByName("Custom Field 1");
        TextField textField1 = (TextField) customField1.getField();
        textField1.setValue(issue, "Value for Custom Field 1");

        assertNotNull(textField1);
        assertEquals("Value for Custom Field 1", textField1.getValue(issue));
    }

    @Test
    public void testAddCustomField2() {
        CustomField customField2 = fieldManager.getCustomFieldObjectByName("Custom Field 2");
        TextField textField2 = (TextField) customField2.getField();
        textField2.setValue(issue, "Value for Custom Field 2");

        assertNotNull(textField2);
        assertEquals("Value for Custom Field 2", textField2.getValue(issue));
    }

    @Test
    public void testAddUser() {
        User user = componentManager.getUserManager().getUserByKey("username");
        issue.addWatcher(user);

        assertNotNull(issue.getWatchers());
        assertTrue(issue.getWatchers().contains(user));
    }

    @Test
    public void testUpdateIssue() {
        try {
            issue.update();
        } catch (Exception e) {
            fail("Error saving issue: " + e.getMessage());
        }
    }

    @Test
    public void testAddCustomField1WithNullValue() {
        CustomField customField1 = fieldManager.getCustomFieldObjectByName("Custom Field 1");
        TextField textField1 = (TextField) customField1.getField();
        textField1.setValue(issue, null);

        assertNull(textField1.getValue(issue));
    }

    @Test
    public void testAddCustomField2WithNullValue() {
        CustomField customField2 = fieldManager.getCustomFieldObjectByName("Custom Field 2");
        TextField textField2 = (TextField) customField2.getField();
        textField2.setValue(issue, null);

        assertNull(textField2.getValue(issue));
    }

    @Test
    public void testAddUserWithNullValue() {
        User user = componentManager.getUserManager().getUserByKey(null);
        issue.addWatcher(user);

        assertNull(issue.getWatchers());
    }
}