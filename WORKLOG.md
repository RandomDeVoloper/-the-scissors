# The Scissors — Çalışma Günlüğü

Bu dosya, proje üzerinde yapılan çalışmaların ve önemli kararların kısa, izlenebilir kaydıdır. Her görev sonunda güncellenir.

## Proje

- Motor: Unreal Engine 5.8.x
- Proje: `SurvivorsTemplate.uproject`
- Çalışma dizini: `C:\\Users\\Niyazi\\-the-scissors`
- Ana konu: Survivor tarzı oynanış, BabyDoll karakteri ve Scissor Snip başlangıç/level-up yeteneği.

## Bilinen önemli asset'ler

- Karakter: `Content/SurvivorsTemplate/Blueprints/Character/BP_BabyDoll.uasset`
- Temel karakter: `Content/SurvivorsTemplate/Blueprints/Character/BP_Base_Character.uasset`
- Yetenek sistemi: `Content/SurvivorsTemplate/Blueprints/Character/BP_Abilities_Component.uasset`
- Save Game: `Content/SurvivorsTemplate/Blueprints/Saves/BP_SG_Player.uasset`
- Karakter tablosu: `Content/SurvivorsTemplate/Blueprints/DataTables/DT_AvailableCharacters.uasset`
- Yetenek tablosu: `Content/SurvivorsTemplate/Blueprints/DataTables/DT_ActiveAbilities.uasset`

## Scissor Snip durumu

- Scissor Snip level-up seçimlerinde görünür durumda.
- `DT_ActiveAbilities` içinde `ScissorSnip1`–`ScissorSnip5` satırları mevcut.
- `integrate_scissor_snip_levelup.py`, Scissor Snip kartlarını ve level-up bağlantısını eklemek için kullanılmıştır.
- Daha önce `DT_AvailableCharacters/Char1` başlangıç yeteneği `Scissor Snip` yapılınca mevcut başlangıç sistemi bozuldu.
- Bu değişiklik geri alındı; `Char1` tekrar `Hammer` değerine getirildi ve Unreal Output Log üzerinden kayıt doğrulandı.
- Scissor Snip'i başlangıç yeteneği yapmak için yalnızca DataTable satırını değiştirmek yeterli değildir. Blueprint başlangıç yeteneği akışı, save data ve `EvolutionTracker` başlatma mantığı birlikte incelenmelidir.

## Son görülen uyarılar

- `BP_Abilities_Component` içinde boş `EvolutionTracker` dizisine indeksle erişim uyarıları görüldü.
- Bazı PIE oturumlarında `CallFunc_ComponentOverlapActors_OutActors_1` dizisi boşken 0. elemana erişim uyarısı görüldü.
- `EOS_Auth_InvalidToken` ve RecastNavMesh uyarıları da görüldü; bunlar Scissor Snip değişikliğinden bağımsız olabilir.

## Mevcut değişiklikler

Önceden kullanıcı tarafından yapılmış olabilecek değişiklikler korunmalıdır. Git durumunda daha önce görülen dosyalar:

- `BP_BabyDoll.uasset`
- `BP_Base_Character.uasset`
- `BP_SG_Player.uasset`
- `DT_AvailableCharacters.uasset`

Bu dosyalar kullanıcı açıkça istemedikçe `git restore`, `git checkout` veya benzeri yıkıcı işlemlerle geri alınmamalıdır.

## Kullanılan yardımcı script'ler

- `tools/create_scissor_snip.py`
- `tools/attach_scissor_snip.py`
- `tools/integrate_scissor_snip_levelup.py`
- `tools/create_abp_babydoll.py`

## Skill kullanım kuralları

Skill dosyaları Codex'in çalışma talimatlarıdır; bu Markdown dosyası onları otomatik olarak yüklemez. Her görevde yalnızca ilgili skill'in güncel `SKILL.md` dosyası okunur.

- Unreal Blueprint işi: `unreal-blueprints`
- Unreal Editor üzerinden canlı asset/Blueprint değişikliği: `unreal-engine-skills-for-codex:unreal-mcp`
- Enhanced Input: `unreal-enhanced-input`
- Niagara/VFX: `unreal-niagara`
- Ses: `ue-audio-system`
- Material/rendering: `ue-materials-rendering`
- Oynanış geri bildirimi: `game-feel`
- Performans: `performance-optimization`
- Paketleme: `unreal-packaging`

Skill'ler baştan topluca yüklenmez; görev kapsamına göre seçilir ve talimatları o görev başlamadan okunur.

## Çalışma ilkeleri

- Unreal binary asset'leri doğrudan metin olarak düzenlenmez.
- Önce mevcut kullanıcı değişiklikleri ve Git durumu kontrol edilir.
- İlgisiz asset'lere dokunulmaz.
- Blueprint değişikliğinden sonra compile/save ve mümkünse PIE doğrulaması yapılır.
- Doğrulanmayan sonuç kesinleşmiş gibi yazılmaz.
- Her önemli işlem bu dosyaya tarihli bir kayıt olarak eklenir.

## Güncel kayıtlar

### 2026-11-26 — Çalışma günlüğü yeniden oluşturuldu

- Discard sonrası `WORKLOG.md` yeniden oluşturuldu.
- Scissor Snip başlangıç denemesinin geri alındığı ve mevcut teknik durum kaydedildi.
- Sonraki adım: başlangıç yeteneği Blueprint akışını inceleyerek Scissor Snip desteğini sistemi bozmadan tasarlamak.

### 2026-11-26 — Save verisi sonrası Scissor Snip tekrar denendi

- Save verisinin eski başlangıç yeteneğini tekrar yazdığı varsayımıyla `DT_AvailableCharacters/Char1` yeniden `Scissor Snip` yapıldı.
- Asset Unreal Editor Python konsolu üzerinden kaydedildi; PIE başlatıldı ve oturum çalıştı.
- Test sonrasında geçici script silindi. Başlangıç silahının oyun içindeki görünümü henüz kesin olarak doğrulanmış sayılmıyor; gerekirse save akışı ve runtime oyuncu yetenekleri ayrı izlenecek.


### 2026-11-26 - Gercek baslangic kaynagi duzeltildi

- `BP_Base_Character` Class Default Object icindeki `StartingAbility` alaninin dogrudan `E_ActiveAbilities.HAMMER` oldugu tespit edildi.
- Alan `E_ActiveAbilities.SCISSOR_SNIP` yapildi; Blueprint compile edildi ve asset kalici olarak kaydedildi.
- PIE oturumu baslatilip durduruldu. `EvolutionTracker` bos dizi uyarilari ayri bir hata olarak devam ediyor.

### 2026-11-26 - Scissor Snip baslangic yetenegi tamamlandi

- Kök neden bulundu: `BP_Abilities_Component > SetStartingAbility` içindeki `Switch on E_ActiveAbilities` düğümünün `Scissor Snip` çıkışı boştu.
- `Level Up Scissor Snip` çağrısı eklendi ve Scissor dalına bağlandı.
- `BP_Abilities_Component` başarıyla compile edildi; PIE testinde Scissor Snip çalıştı.
