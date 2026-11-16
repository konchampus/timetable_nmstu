import {useEffect,useState} from 'react';
import {BookOpen,Check,Code2,Fish,GitCommitHorizontal,LockKeyhole,Mountain,PawPrint,UserRound,ChevronDown} from 'lucide-react';
import {points,type Inventory,type FishingLocationId,type FishingSkinId} from './types';

interface Props {
  inventory:Inventory|null;
  location:FishingLocationId;
  skin:FishingSkinId;
  disabled:boolean;
  locked:boolean;
  onChange:(value:{location:FishingLocationId;skin:FishingSkinId})=>void;
}
const locationIcons={shore:Fish,river:Code2,mountain:Mountain,golden:GitCommitHorizontal};
export default function FishingSetup({inventory,location,skin,disabled,locked,onChange}:Props){
  const [previewId,setPreviewId]=useState<FishingLocationId|null>(null);
  useEffect(()=>setPreviewId(null),[location]);
  const locations=inventory?.locations??[],skins=inventory?.skins??[];
  const chosen=locations.find(item=>item.id===location);
  const preview=locations.find(item=>item.id===previewId)??chosen;
  if(inventory?.world_version!==1)return <p className="fishing-world-unavailable" role="status">Новые локации появятся после обновления сервера. Пока доступен обычный берег.</p>;
  return <section className="fishing-expedition" aria-labelledby="fishing-trip-title">
    <div className="fishing-trip-heading">
      <div><h3 id="fishing-trip-title">Куда отправимся?</h3><p>{locked?'Место и скин закреплены до конца текущей ловли.':'У каждого места своя история. Выберите доступное или загляните в легенду закрытого.'}</p></div>
      <span>Удочка {inventory.rod_level} ур.</span>
    </div>
    <div className="fishing-destinations" role="group" aria-label="Локации и их истории">
      {locations.map(item=>{
        const Icon=locationIcons[item.id];
        return <button type="button" key={item.id} className={'fishing-destination destination-'+item.theme+(preview?.id===item.id?' is-preview':'')}
          aria-pressed={location===item.id} aria-controls="fishing-location-description" disabled={disabled||locked}
          onClick={()=>{setPreviewId(item.id);if(item.unlocked)onChange({location:item.id,skin});}}>
          <span className="destination-landscape" aria-hidden="true"><Icon size={28}/>{location===item.id?<Check size={18}/>:!item.unlocked?<LockKeyhole size={18}/>:null}</span>
          <strong>{item.title}</strong>
          {item.tagline&&<span className="destination-theme">{item.tagline}</span>}
          <span>{item.unlocked?'Доступна · выбрать':'С '+item.min_rod_level+' ур. · посмотреть'}</span>
          <b>Стоимость улова ×{points(item.value_multiplier)}</b>
        </button>;
      })}
    </div>
    {preview&&<div id="fishing-location-description" className="fishing-destination-detail" key={preview.id}>
      {!preview.unlocked&&<div className="fishing-locked-preview" role="status"><LockKeyhole size={17}/><p>Это только знакомство с местом. Для ловли нужна удочка {preview.min_rod_level} ур.; следующий заброс остаётся в локации «{chosen?.title}».</p></div>}
      <p>{preview.description}</p>
      {preview.story&&<details className="fishing-lore">
        <summary><BookOpen size={18}/><span>Игровая легенда: {preview.story_title}</span><ChevronDown size={16}/></summary>
        <p>{preview.story}</p>
        {preview.landmark&&<p className="fishing-landmark">В 3D-сцене: {preview.landmark.toLocaleLowerCase('ru')}.</p>}
        {!!preview.featured_species?.length&&<p className="fishing-story-fish">Герои этой истории: {preview.featured_species.join(' и ')}. Остальной улов смотрите в таблице.</p>}
      </details>}
      <details>
        <summary>Что здесь можно поймать <ChevronDown size={16}/></summary>
        <p>{!preview.unlocked?'Предпросмотр для удочки '+preview.preview_rod_level+' ур. ':''}Шанс вида при успешном вываживании, удочка {preview.preview_rod_level} ур. Вес не влияет на стоимость одной рыбы.</p>
        <div className="fishing-pool" role="list">{preview.fish.map(fish=><div role="listitem" key={fish.species}>
          <span><strong>{fish.species}</strong><small>{points(fish.min_weight)}–{points(fish.max_weight)} кг</small></span>
          <span>{points(fish.probability*100)}%<strong>{points(fish.value)} очк.</strong></span>
        </div>)}</div>
      </details>
    </div>}
    <fieldset className="fishing-skins" disabled={disabled||locked}>
      <legend>Ваш персонаж <span>Только внешний вид, без бонусов</span></legend>
      <div>{skins.map(item=><label key={item.id}>
        <input type="radio" name="fishing-skin" value={item.id} checked={skin===item.id} disabled={!item.unlocked} onChange={()=>onChange({location,skin:item.id})}/>
        <span>{item.id==='bear'?<PawPrint size={22}/>:<UserRound size={22}/>}<span><strong>{item.title}</strong><small>{item.unlocked?'Бесплатно':'Удочка '+item.min_rod_level+' ур.'}</small></span>{!item.unlocked?<LockKeyhole size={16}/>:skin===item.id?<Check size={18}/>:null}</span>
      </label>)}</div>
    </fieldset>
    {!locked&&<p className="fishing-selection-note">Следующий заброс: <strong>{chosen?.title??'Пруд старого карася'}</strong> · {skins.find(item=>item.id===skin)?.title??'Рыбак'}. Выбор сохранится на сервере при забросе.</p>}
  </section>;
}
