# Human review packet — `php-web-v0.1`

> **Decision authority:** Oleksii Siniaiev. Everything below is an agent recommendation, not ground truth. No case may be frozen until Oleksii explicitly accepts or changes it. `academic_review` remains false unless review by Valeriia Chumak is explicitly confirmed.

For each case, reply **ACCEPT**, **MODIFY: ...**, or **REMOVE**. The displayed context and diff are exactly what the evaluated model receives (inside the versioned reviewer prompt).

## laravel-authz-001

- **Source / ecosystem / category:** `synthetic` / `laravel` / `authorization`
- **Expected:** `authorization_policy_removed` / **high** — The $this->authorize('update', $post) call was removed, so any authenticated user can update any post.
- **Decidable because:** Policy existence, registration and authenticated-only route make the missing object authorization decidable.
- **Plausible alternative:** UpdatePostRequest could authorize, but the supplied context makes the policy call the stated control.
- **Second-defect check:** No second defect: validated input and route behaviour are unchanged.
- **Provenance:** Original synthetic fixture.
- **Agent recommendation:** **ACCEPT**

**Supplied description:** A refactor of the post update action removes the policy check that restricted updates to users authorised for the post.

**Supplied context:** The application uses Laravel policies. PostPolicy::update() exists and is registered. The route is inside the 'auth' middleware group, so the user is authenticated but not necessarily the owner of the post.

```diff
diff --git a/app/Http/Controllers/PostController.php b/app/Http/Controllers/PostController.php
--- a/app/Http/Controllers/PostController.php
+++ b/app/Http/Controllers/PostController.php
@@ -32,12 +32,10 @@ class PostController extends Controller

     public function update(UpdatePostRequest $request, Post $post): RedirectResponse
     {
-        $this->authorize('update', $post);
-
         $post->update($request->validated());

         return redirect()
             ->route('posts.show', $post)
             ->with('status', 'Post updated.');
     }
```

## laravel-authz-002

- **Source / ecosystem / category:** `synthetic` / `laravel` / `authorization`
- **Expected:** `authorization_middleware_removed` / **critical** — The admin routes no longer run the 'auth' and 'can:admin' middleware, exposing user administration endpoints to unauthenticated requests.
- **Decidable because:** The context excludes controller checks and other middleware.
- **Plausible alternative:** A deployment-level gate could protect the routes, but it is explicitly outside the supplied facts.
- **Second-defect check:** All three exposed routes are one removed middleware-boundary defect.
- **Provenance:** Original synthetic fixture.
- **Agent recommendation:** **ACCEPT**

**Supplied description:** Admin routes are lifted out of the middleware group while reorganising routes/web.php, leaving them without authentication or the admin gate.

**Supplied context:** The 'can:admin' gate is defined in AuthServiceProvider. No other middleware is applied to these routes elsewhere; the controller does not perform its own checks.

```diff
diff --git a/routes/web.php b/routes/web.php
--- a/routes/web.php
+++ b/routes/web.php
@@ -18,12 +18,10 @@ Route::get('/posts/{post}', [PostController::class, 'show'])->name('posts.show')

-Route::middleware(['auth', 'can:admin'])->group(function () {
-    Route::get('/admin/users', [AdminUserController::class, 'index'])->name('admin.users');
-    Route::post('/admin/users/{user}/promote', [AdminUserController::class, 'promote']);
-    Route::delete('/admin/users/{user}', [AdminUserController::class, 'destroy']);
-});
+Route::get('/admin/users', [AdminUserController::class, 'index'])->name('admin.users');
+Route::post('/admin/users/{user}/promote', [AdminUserController::class, 'promote']);
+Route::delete('/admin/users/{user}', [AdminUserController::class, 'destroy']);
```

## laravel-clean-001

- **Source / ecosystem / category:** `synthetic` / `laravel` / `clean_control`
- **Expected:** **CLEAN** (no expected findings)
- **Decidable because:** The policy call remains and the two literal fields are explicitly fillable.
- **Plausible alternative:** A reviewer may treat fill() as mass assignment regardless of its literal input.
- **Second-defect check:** No accidental defect; formatting and save semantics remain equivalent.
- **Strongest false-alarm temptation:** A reviewer may treat fill() as mass assignment regardless of its literal input.
- **Provenance:** Original synthetic fixture.
- **Agent recommendation:** **ACCEPT**

**Supplied description:** Three attribute assignments are collapsed into fill()/save(). Behaviour, authorisation and validation are unchanged.

**Supplied context:** Invoice::$fillable includes both status and paid_at, so fill() will not silently discard either value. The authorize() call and InvoicePolicy are unchanged and visible as context lines in the diff.

```diff
diff --git a/app/Http/Controllers/InvoiceController.php b/app/Http/Controllers/InvoiceController.php
--- a/app/Http/Controllers/InvoiceController.php
+++ b/app/Http/Controllers/InvoiceController.php
@@ -40,13 +40,15 @@ class InvoiceController extends Controller

     public function markPaid(MarkInvoicePaidRequest $request, Invoice $invoice): RedirectResponse
     {
         $this->authorize('markPaid', $invoice);

-        $invoice->status = 'paid';
-        $invoice->paid_at = now();
-        $invoice->save();
+        $invoice->fill([
+            'status'  => 'paid',
+            'paid_at' => now(),
+        ]);
+
+        $invoice->save();

         return back()->with('status', 'Invoice marked as paid.');
     }
```

## laravel-ghsa-debug-xss-001

- **Source / ecosystem / category:** `public_advisory` / `laravel` / `xss`
- **Expected:** `xss_unescaped_output` / **medium** — Changing the body expression to raw Blade output lets request-controlled HTML be parsed in the diagnostic page, introducing reflected XSS. The previous escaped expression displayed the same body as text.
- **Decidable because:** The context pins attacker-controlled HTML, a reachable HTML response and no later mitigation.
- **Plausible alternative:** A locked-down debug endpoint would lower exploitability, but reachability is supplied.
- **Second-defect check:** No separate information-disclosure label; diagnostics exposure is a stated precondition.
- **Provenance:** Advisory-derived synthetic reconstruction of `GHSA-546h-56qp-8jmw` for laravel/framework; not upstream code or an upstream patch. Source: https://github.com/advisories/GHSA-546h-56qp-8jmw
- **Agent recommendation:** **ACCEPT**

**Supplied description:** Change how the request body is rendered in the diagnostic panel.

**Supplied context:** This Blade view is rendered as text/html on a development diagnostic endpoint. $submittedBody is a plain PHP string containing the raw request body, including any HTML characters supplied by the visitor; it is not an Htmlable object. The endpoint is reachable by visitors and its page can be viewed by another user. Debug access itself is unchanged and in scope only as a stated precondition. No filter, sanitizer, escaping wrapper or script-blocking CSP runs after this view. No credentials or other diagnostic data are displayed. Blade {{ }} HTML-escapes strings; {!! !!} outputs them verbatim.

```diff
diff --git a/resources/views/diagnostics/body.blade.php b/resources/views/diagnostics/body.blade.php
--- a/resources/views/diagnostics/body.blade.php
+++ b/resources/views/diagnostics/body.blade.php
@@ -1,4 +1,4 @@
 <section aria-label="Request diagnostics">
     <h2>Submitted body</h2>
-    <pre><code>{{ $submittedBody }}</code></pre>
+    <pre><code>{!! $submittedBody !!}</code></pre>
 </section>
```

## laravel-ghsa-env-001

- **Source / ecosystem / category:** `public_advisory` / `laravel` / `injection`
- **Expected:** `environment_override_from_web_argv` / **high** — Removing the CLI-only guard lets request-controlled web argv values enter the --env= option parser and override the trusted deployment environment. This is configuration injection across the web/CLI trust boundary, not SQL injection or proof of a downstream exploit.
- **Decidable because:** The context pins CGI argv as request-controlled and the return value as configuration selection.
- **Plausible alternative:** Some deployments do not populate web argv; this fixture explicitly does.
- **Second-defect check:** Do not infer RCE, debug exposure or .env loading; none is supplied.
- **Provenance:** Advisory-derived synthetic reconstruction of `GHSA-gv7v-rgg6-548h` for laravel/framework; not upstream code or an upstream patch. Source: https://github.com/laravel/framework/security/advisories/GHSA-gv7v-rgg6-548h
- **Agent recommendation:** **ACCEPT**

**Supplied description:** Simplify the argument scan in the shared environment selector.

**Supplied context:** This PHP 8+ bootstrap helper serves a Laravel-style application's web and CLI entry points. The caller passes PHP_SAPI as $sapi, $_SERVER['argv'] ?? [] as $arguments (a list of strings), and a trusted deployment environment name as $configured. Web requests run with SAPI cgi-fcgi and register_argc_argv enabled; this deployment populates argv from the request query string, so a remote caller can control those argument strings. On cli the arguments are intentionally operator-controlled. The returned name selects the application's runtime environment and its environment-specific configuration; web requests must retain $configured. There is no other SAPI gate or validation before this function. This fixture models environment selection only, not .env file loading, debug enablement, command execution or any downstream vulnerability.

```diff
diff --git a/app/Bootstrap/environment.php b/app/Bootstrap/environment.php
--- a/app/Bootstrap/environment.php
+++ b/app/Bootstrap/environment.php
@@ -1,14 +1,12 @@
 <?php
 function selectRuntimeEnvironment(string $sapi, array $arguments, string $configured): string
 {
     $selected = $configured;
-    if ($sapi === 'cli') {
-        foreach ($arguments as $argument) {
-            if (str_starts_with($argument, '--env=')) {
-                $selected = substr($argument, 6);
-                break;
-            }
+    foreach ($arguments as $argument) {
+        if (str_starts_with($argument, '--env=')) {
+            $selected = substr($argument, 6);
+            break;
         }
     }
     return $selected;
 }
```

## laravel-ghsa-env-clean-001

- **Source / ecosystem / category:** `public_advisory` / `laravel` / `clean_control`
- **Expected:** **CLEAN** (no expected findings)
- **Decidable because:** The early non-CLI return prevents web input from reaching the option scan.
- **Plausible alternative:** A reviewer may flag returning argv-derived values without noticing it occurs only for operator-controlled CLI.
- **Second-defect check:** Empty CLI values are pre-existing behaviour, not a new web defect.
- **Strongest false-alarm temptation:** A reviewer may flag returning argv-derived values without noticing it occurs only for operator-controlled CLI.
- **Provenance:** Advisory-derived synthetic reconstruction of `GHSA-gv7v-rgg6-548h` for laravel/framework; not upstream code or an upstream patch. Source: https://github.com/laravel/framework/security/advisories/GHSA-gv7v-rgg6-548h
- **Agent recommendation:** **ACCEPT**

**Supplied description:** Refactor environment selection to return immediately for web requests and matching console arguments.

**Supplied context:** This PHP 8+ bootstrap helper serves a Laravel-style application's web and CLI entry points. The caller passes PHP_SAPI as $sapi, $_SERVER['argv'] ?? [] as $arguments (a list of strings), and a trusted deployment environment name as $configured. Web requests run with SAPI cgi-fcgi and register_argc_argv enabled; this deployment populates argv from the request query string, so a remote caller can control those argument strings. On cli the arguments are intentionally operator-controlled. The returned name selects the application's runtime environment and its environment-specific configuration; web requests must retain $configured. There is no other SAPI gate or validation before this function. This fixture models environment selection only, not .env file loading, debug enablement, command execution or any downstream vulnerability.

```diff
diff --git a/app/Bootstrap/environment.php b/app/Bootstrap/environment.php
--- a/app/Bootstrap/environment.php
+++ b/app/Bootstrap/environment.php
@@ -1,14 +1,13 @@
 <?php
 function selectRuntimeEnvironment(string $sapi, array $arguments, string $configured): string
 {
-    $selected = $configured;
-    if ($sapi === 'cli') {
-        foreach ($arguments as $argument) {
-            if (str_starts_with($argument, '--env=')) {
-                $selected = substr($argument, 6);
-                break;
-            }
+    if ($sapi !== 'cli') {
+        return $configured;
+    }
+    foreach ($arguments as $argument) {
+        if (str_starts_with($argument, '--env=')) {
+            return substr($argument, 6);
         }
     }
-    return $selected;
+    return $configured;
 }
```

## laravel-injection-001

- **Source / ecosystem / category:** `synthetic` / `laravel` / `injection`
- **Expected:** `sql_injection` / **critical** — Request input is concatenated into a raw SQL string passed to DB::select(), allowing SQL injection. Bindings or the query builder should be used.
- **Decidable because:** Unvalidated request input is visibly concatenated into executable SQL.
- **Plausible alternative:** A database allow-list could mitigate it, but the context excludes one.
- **Second-defect check:** No output sink or authorization change supplies a second defect.
- **Provenance:** Original synthetic fixture.
- **Agent recommendation:** **ACCEPT**

**Supplied description:** A report search is rewritten from the query builder to a raw SQL string that concatenates a request parameter.

**Supplied context:** $request->input('email') is unvalidated user input taken from the query string. No database-level allow-list or escaping is applied elsewhere in the request cycle.

```diff
diff --git a/app/Http/Controllers/ReportController.php b/app/Http/Controllers/ReportController.php
--- a/app/Http/Controllers/ReportController.php
+++ b/app/Http/Controllers/ReportController.php
@@ -21,12 +21,14 @@ class ReportController extends Controller

     public function search(Request $request): View
     {
-        $rows = DB::table('orders')
-            ->where('customer_email', $request->input('email'))
-            ->orderByDesc('created_at')
-            ->get();
+        $email = $request->input('email');
+
+        $rows = DB::select(
+            "SELECT id, total, created_at FROM orders "
+            . "WHERE customer_email = '" . $email . "' ORDER BY created_at DESC"
+        );

         return view('reports.search', ['rows' => $rows]);
     }
```

## laravel-xss-001

- **Source / ecosystem / category:** `synthetic` / `laravel` / `xss`
- **Expected:** `xss_unescaped_output` / **high** — User-submitted comment bodies are rendered unescaped with {!! !!}, allowing stored cross-site scripting.
- **Decidable because:** Free-text user content moves from escaped to raw Blade output with no sanitizer.
- **Plausible alternative:** Trusted markup would make raw output intentional, but context says any registered user supplies unsanitized text.
- **Second-defect check:** Author name remains escaped; only the body sink changes.
- **Provenance:** Original synthetic fixture.
- **Agent recommendation:** **ACCEPT**

**Supplied description:** A Blade partial switches from escaped output to {!! !!} so that stored comment markup renders as HTML.

**Supplied context:** comment.body is free text submitted by any registered user. The application does not sanitise comment bodies on write and has no output-filtering middleware.

```diff
diff --git a/resources/views/comments/_comment.blade.php b/resources/views/comments/_comment.blade.php
--- a/resources/views/comments/_comment.blade.php
+++ b/resources/views/comments/_comment.blade.php
@@ -1,8 +1,8 @@
 <article class="comment" id="comment-{{ $comment->id }}">
     <h4 class="comment-author">{{ $comment->author_name }}</h4>

-    <div class="comment-body">{{ $comment->body }}</div>
+    <div class="comment-body">{!! $comment->body !!}</div>

     <time datetime="{{ $comment->created_at->toIso8601String() }}">
         {{ $comment->created_at->diffForHumans() }}
     </time>
 </article>
```

## php-clean-001

- **Source / ecosystem / category:** `synthetic` / `php` / `clean_control`
- **Expected:** **CLEAN** (no expected findings)
- **Decidable because:** The same named PDO parameter remains bound and LIMIT 1 matches the single-row API.
- **Plausible alternative:** A reviewer may flag SQL because the query text changed.
- **Second-defect check:** No concatenation or changed trust boundary exists.
- **Strongest false-alarm temptation:** A reviewer may flag SQL because the query text changed.
- **Provenance:** Original synthetic fixture.
- **Agent recommendation:** **ACCEPT**

**Supplied description:** A PDO lookup is reformatted and gains a LIMIT 1. The statement stays parameterised and the behaviour is unchanged for the caller.

**Supplied context:** $email arrives already validated by the caller and is bound as a named parameter both before and after the change.

```diff
diff --git a/src/Repository/UserRepository.php b/src/Repository/UserRepository.php
--- a/src/Repository/UserRepository.php
+++ b/src/Repository/UserRepository.php
@@ -14,12 +14,16 @@ final class UserRepository

     public function findByEmail(string $email): ?array
     {
-        $stmt = $this->pdo->prepare('SELECT id, email, name FROM users WHERE email = :email');
-        $stmt->execute(['email' => $email]);
-        $row = $stmt->fetch(PDO::FETCH_ASSOC);
+        $statement = $this->pdo->prepare(
+            'SELECT id, email, name FROM users WHERE email = :email LIMIT 1'
+        );
+
+        $statement->execute(['email' => $email]);
+
+        $row = $statement->fetch(PDO::FETCH_ASSOC);

         return $row === false ? null : $row;
     }
```

## php-injection-001

- **Source / ecosystem / category:** `synthetic` / `php` / `injection`
- **Expected:** `sql_injection` / **critical** — The search term from $_GET is concatenated into the SQL string passed to mysqli_query(), replacing a prepared statement and allowing SQL injection.
- **Decidable because:** Raw GET input is visibly concatenated after removal of the prepared statement.
- **Plausible alternative:** Input validation could constrain it, but the context excludes filtering.
- **Second-defect check:** HTML output is still escaped, so XSS is not a second defect.
- **Provenance:** Original synthetic fixture.
- **Agent recommendation:** **ACCEPT**

**Supplied description:** A legacy search endpoint drops its prepared statement in favour of mysqli_query() with the search term concatenated into the SQL.

**Supplied context:** $_GET['term'] is unfiltered user input. The connection uses the default character set and no input filter runs before this file.

```diff
diff --git a/src/Legacy/search.php b/src/Legacy/search.php
--- a/src/Legacy/search.php
+++ b/src/Legacy/search.php
@@ -10,13 +10,12 @@ require __DIR__ . '/bootstrap.php';

-$like = '%' . $_GET['term'] . '%';
-
-$stmt = $mysqli->prepare('SELECT id, title FROM articles WHERE title LIKE ?');
-$stmt->bind_param('s', $like);
-$stmt->execute();
-$result = $stmt->get_result();
+$term = $_GET['term'];
+
+$result = mysqli_query(
+    $mysqli,
+    "SELECT id, title FROM articles WHERE title LIKE '%" . $term . "%'"
+);

 while ($row = $result->fetch_assoc()) {
     echo '<li>' . htmlspecialchars($row['title'], ENT_QUOTES) . '</li>';
 }
```

## php-secrets-001

- **Source / ecosystem / category:** `synthetic` / `php` / `secrets`
- **Expected:** `hardcoded_secret` / **high** — A mailer API key literal is committed to the repository instead of being read from the environment.
- **Decidable because:** A key-shaped literal is introduced in a tracked deployed file.
- **Plausible alternative:** The literal is fabricated, but committing credential material is the behaviour under test.
- **Second-defect check:** The example endpoint and timeout do not introduce another defect.
- **Provenance:** Original synthetic fixture.
- **Agent recommendation:** **ACCEPT**

**Supplied description:** An environment lookup for the mailer API key is replaced by a literal value committed to the repository.

**Supplied context:** config/services.php is tracked in version control and deployed to all environments. The repository has no secret-scanning hook.

```diff
diff --git a/config/services.php b/config/services.php
--- a/config/services.php
+++ b/config/services.php
@@ -8,9 +8,9 @@ return [

     'mailer' => [
         'endpoint' => 'https://api.mailer.example/v1',
-        'api_key'  => getenv('WFB_MAILER_API_KEY') ?: '',
+        'api_key'  => 'wfb_live_EXAMPLE_NOT_A_REAL_KEY_2f9c1d',
         'timeout'  => 10,
     ],
 ];
```

## wp-authz-001

- **Source / ecosystem / category:** `synthetic` / `wordpress` / `authorization`
- **Expected:** `authorization_capability_missing` / **high** — The new wp_ajax_wfb_export_subscribers handler exports subscriber e-mail addresses without a current_user_can() capability check, so any logged-in user with a valid nonce can call it.
- **Decidable because:** The hook admits any logged-in user and context excludes a shared permission wrapper.
- **Plausible alternative:** A nonce may look like authorization, but it verifies intent rather than capability.
- **Second-defect check:** Prepared SQL and integer coercion exclude injection; nonce excludes the intended CSRF finding.
- **Provenance:** Original synthetic fixture.
- **Agent recommendation:** **ACCEPT**

**Supplied description:** A plugin adds an AJAX endpoint that exports subscriber e-mail addresses. The request nonce and SQL handling are correct, but the handler performs no capability check.

**Supplied context:** add_action('wp_ajax_...') registers the handler for any logged-in user, including subscribers. The client sends a valid wfb_export_subscribers nonce. There is no shared permission wrapper in this plugin; each handler performs its own capability check.

```diff
diff --git a/wp-content/plugins/wfb-demo/includes/ajax.php b/wp-content/plugins/wfb-demo/includes/ajax.php
--- a/wp-content/plugins/wfb-demo/includes/ajax.php
+++ b/wp-content/plugins/wfb-demo/includes/ajax.php
@@ -58,3 +58,23 @@ function wfb_ajax_rename_list() {

     wp_send_json_success( array( 'name' => esc_html( $name ) ) );
 }
+
+add_action( 'wp_ajax_wfb_export_subscribers', 'wfb_ajax_export_subscribers' );
+
+function wfb_ajax_export_subscribers() {
+    check_ajax_referer( 'wfb_export_subscribers' );
+
+    global $wpdb;
+
+    $list_id = isset( $_POST['list_id'] ) ? absint( $_POST['list_id'] ) : 0;
+
+    $rows = $wpdb->get_results(
+        $wpdb->prepare(
+            "SELECT email FROM {$wpdb->prefix}wfb_subscribers WHERE list_id = %d",
+            $list_id
+        )
+    );
+
+    wp_send_json_success( wp_list_pluck( $rows, 'email' ) );
+}
```

## wp-clean-001

- **Source / ecosystem / category:** `synthetic` / `wordpress` / `clean_control`
- **Expected:** **CLEAN** (no expected findings)
- **Decidable because:** Nonce, capability gate, typed database formats and JSON serialization all remain.
- **Plausible alternative:** A reviewer may demand HTML escaping for a value returned as JSON.
- **Second-defect check:** Direct $_POST access is pre-existing; the change adds sanitization.
- **Strongest false-alarm temptation:** A reviewer may demand HTML escaping for a value returned as JSON.
- **Provenance:** Original synthetic fixture.
- **Agent recommendation:** **ACCEPT**

**Supplied description:** An existing AJAX handler is improved by sanitising the submitted name. The nonce, capability check, safe database API and JSON response semantics are unchanged.

**Supplied context:** check_ajax_referer() and current_user_can('manage_options') remain in place and are visible as context lines. $wpdb->update() uses format specifiers.

```diff
diff --git a/wp-content/plugins/wfb-demo/includes/ajax.php b/wp-content/plugins/wfb-demo/includes/ajax.php
--- a/wp-content/plugins/wfb-demo/includes/ajax.php
+++ b/wp-content/plugins/wfb-demo/includes/ajax.php
@@ -38,21 +38,21 @@ add_action( 'wp_ajax_wfb_rename_list', 'wfb_ajax_rename_list' );

 function wfb_ajax_rename_list() {
     check_ajax_referer( 'wfb_rename_list' );

     if ( ! current_user_can( 'manage_options' ) ) {
         wp_send_json_error( array( 'message' => 'Not allowed.' ), 403 );
     }

     global $wpdb;

     $list_id = isset( $_POST['list_id'] ) ? absint( $_POST['list_id'] ) : 0;
-    $name    = wp_unslash( $_POST['name'] );
+    $name    = sanitize_text_field( wp_unslash( $_POST['name'] ) );

     $wpdb->update(
         $wpdb->prefix . 'wfb_lists',
         array( 'name' => $name ),
         array( 'id' => $list_id ),
         array( '%s' ),
         array( '%d' )
     );

     wp_send_json_success( array( 'name' => $name ) );
 }
```

## wp-deser-001

- **Source / ecosystem / category:** `synthetic` / `wordpress` / `unsafe_deserialization`
- **Expected:** `unsafe_deserialization` / **high** — unserialize() is called on an unsigned, attacker-controlled cookie value, enabling PHP object injection.
- **Decidable because:** An unsigned attacker-controlled cookie reaches unserialize with gadget classes available.
- **Plausible alternative:** allowed_classes=false could narrow object injection, but it is not used.
- **Second-defect check:** The array fallback is post-deserialization and does not prevent gadget execution.
- **Provenance:** Original synthetic fixture.
- **Agent recommendation:** **ACCEPT**

**Supplied description:** A preferences cookie that used to be JSON is now decoded with unserialize(), so attacker-controlled input reaches PHP object instantiation.

**Supplied context:** The cookie is set client-side and is not signed or encrypted. The site loads several plugins, so classes with __destruct()/__wakeup() are present in the runtime.

```diff
diff --git a/wp-content/plugins/wfb-demo/includes/prefs.php b/wp-content/plugins/wfb-demo/includes/prefs.php
--- a/wp-content/plugins/wfb-demo/includes/prefs.php
+++ b/wp-content/plugins/wfb-demo/includes/prefs.php
@@ -3,11 +3,11 @@
 function wfb_get_visitor_prefs() {
     $raw = isset( $_COOKIE['wfb_prefs'] ) ? wp_unslash( $_COOKIE['wfb_prefs'] ) : '';

     if ( '' === $raw ) {
         return array();
     }

-    $prefs = json_decode( $raw, true );
+    $prefs = unserialize( $raw );

     return is_array( $prefs ) ? $prefs : array();
 }
```

## wp-xss-001

- **Source / ecosystem / category:** `synthetic` / `wordpress` / `xss`
- **Expected:** `xss_unescaped_output` / **high** — The query-string parameter wfb_q is echoed without escaping, producing reflected cross-site scripting.
- **Decidable because:** Attacker-controlled query input replaces esc_html in a public HTML sink.
- **Plausible alternative:** A global escaping layer could mitigate it, but context excludes one.
- **Second-defect check:** Result titles remain escaped; only the query reflection is defective.
- **Provenance:** Original synthetic fixture.
- **Agent recommendation:** **ACCEPT**

**Supplied description:** A template stops using esc_html() and concatenates the raw query-string parameter into the echoed markup.

**Supplied context:** $_GET['wfb_q'] is attacker-controllable via a crafted link. The template is rendered on a public page and no output buffering filter escapes it later.

```diff
diff --git a/wp-content/plugins/wfb-demo/templates/search-results.php b/wp-content/plugins/wfb-demo/templates/search-results.php
--- a/wp-content/plugins/wfb-demo/templates/search-results.php
+++ b/wp-content/plugins/wfb-demo/templates/search-results.php
@@ -1,9 +1,9 @@
 <div class="wfb-search-results">
-    <p class="wfb-query">You searched for: <?php echo esc_html( $query ); ?></p>
+    <p class="wfb-query">You searched for: <?php echo '<strong>' . $_GET['wfb_q'] . '</strong>'; ?></p>

     <ul>
         <?php foreach ( $results as $result ) : ?>
             <li><?php echo esc_html( $result->title ); ?></li>
         <?php endforeach; ?>
     </ul>
 </div>
```

