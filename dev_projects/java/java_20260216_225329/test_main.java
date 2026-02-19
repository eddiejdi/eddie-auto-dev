import com.atlassian.jira.component.ComponentManager;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.UserFieldManager;
import com.atlassian.jira.user.ApplicationUser;
import com.atlassian.jira.user.UserManager;

import org.junit.Before;
import org.junit.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

import java.util.HashMap;

public class JavaAgentTest {

    @Mock
    private ComponentManager componentManager;

    @Mock
    private FieldManager fieldManager;

    @Mock
    private UserFieldManager userFieldManager;

    @Mock
    private UserManager userManager;

    @InjectMocks
    private JavaAgent javaAgent;

    @Before
    public void setUp() {
        MockitoAnnotations.openMocks(this);
    }

    @Test
    public void testCreateUserAndUpdateIssue() {
        // Caso de sucesso com valores válidos
        ApplicationUser user = new ApplicationUser("newuser", "password");
        CustomFieldManager customFieldManager = componentManager.getCustomFieldManager();
        CustomField customField = customFieldManager.getCustomFieldByName("My Personal Field");

        if (customField != null) {
            try {
                javaAgent.createUserAndUpdateIssue(user, "issue123", new HashMap<String, Object>() {{
                    put(customField.getName(), "New Value");
                }});
                System.out.println("User updated successfully.");
            } catch (Exception e) {
                System.err.println("Error updating user: " + e.getMessage());
            }
        } else {
            System.err.println("Custom field not found.");
        }

        // Caso de erro (divisão por zero)
        try {
            javaAgent.createUserAndUpdateIssue(user, "issue123", new HashMap<String, Object>() {{
                put(customField.getName(), 0);
            }});
        } catch (Exception e) {
            System.err.println("Error updating user: " + e.getMessage());
        }

        // Caso de erro (valor inválido)
        try {
            javaAgent.createUserAndUpdateIssue(user, "issue123", new HashMap<String, Object>() {{
                put(customField.getName(), "Invalid Value");
            }});
        } catch (Exception e) {
            System.err.println("Error updating user: " + e.getMessage());
        }

        // Caso de erro (edge case: valor limite)
        try {
            javaAgent.createUserAndUpdateIssue(user, "issue123", new HashMap<String, Object>() {{
                put(customField.getName(), Integer.MAX_VALUE);
            }});
        } catch (Exception e) {
            System.err.println("Error updating user: " + e.getMessage());
        }

        // Caso de erro (edge case: string vazia)
        try {
            javaAgent.createUserAndUpdateIssue(user, "issue123", new HashMap<String, Object>() {{
                put(customField.getName(), "");
            }});
        } catch (Exception e) {
            System.err.println("Error updating user: " + e.getMessage());
        }

        // Caso de erro (edge case: None)
        try {
            javaAgent.createUserAndUpdateIssue(user, "issue123", new HashMap<String, Object>() {{
                put(customField.getName(), null);
            }});
        } catch (Exception e) {
            System.err.println("Error updating user: " + e.getMessage());
        }

        // Caso de erro (edge case: empty string)
        try {
            javaAgent.createUserAndUpdateIssue(user, "issue123", new HashMap<String, Object>() {{
                put(customField.getName(), " ");
            }});
        } catch (Exception e) {
            System.err.println("Error updating user: " + e.getMessage());
        }
    }
}